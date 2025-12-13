"""
Authentication System

Implements:
- TOTP-based two-factor authentication (RFC 6238)
- JWT session tokens with refresh
- Brute-force protection with exponential backoff
- Secure session management
"""

import os
import hmac
import time
import base64
import secrets
import hashlib
import logging
import functools
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import json

import jwt
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def _get_user_data_key() -> bytes:
    """
    Derive encryption key for user data from master key or generate a stable one.
    Uses PBKDF2 with a fixed salt for reproducibility.
    """
    master_key = os.getenv('CARBS_MASTER_KEY', os.getenv('CARBS_JWT_SECRET', ''))
    if not master_key:
        # Generate a stable key based on machine-specific info
        import socket
        machine_id = f"carbs-{socket.gethostname()}-user-data"
        master_key = machine_id
        logger.warning("No CARBS_MASTER_KEY set. Using machine-based key for user data encryption.")

    # Fixed salt for user data encryption (reproducibility required)
    salt = b'CARBS_USER_DATA_ENCRYPTION_SALT_'

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,
        backend=default_backend()
    )

    import base64
    return base64.urlsafe_b64encode(kdf.derive(master_key.encode()))


class AuthError(Exception):
    """Authentication error"""
    pass


class TokenError(Exception):
    """Token validation error"""
    pass


@dataclass
class User:
    """User account"""
    user_id: str
    username: str
    password_hash: bytes
    password_salt: bytes
    totp_secret: Optional[str] = None
    totp_enabled: bool = False
    role: str = 'viewer'
    failed_attempts: int = 0
    locked_until: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None


@dataclass
class Session:
    """Active session"""
    session_id: str
    user_id: str
    username: str
    role: str
    ip_address: str
    user_agent: str
    created_at: datetime
    expires_at: datetime
    refresh_token: str
    is_active: bool = True

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at


class TOTP:
    """
    Time-based One-Time Password (RFC 6238)

    Compatible with Google Authenticator, Authy, etc.
    """

    DIGITS = 6
    PERIOD = 30  # seconds
    ALGORITHM = 'SHA1'

    @staticmethod
    def generate_secret() -> str:
        """Generate a new TOTP secret"""
        return base64.b32encode(secrets.token_bytes(20)).decode('utf-8')

    @staticmethod
    def get_totp_token(secret: str, timestamp: Optional[int] = None) -> str:
        """
        Generate TOTP token for given timestamp

        Args:
            secret: Base32-encoded secret
            timestamp: Unix timestamp (current time if None)

        Returns:
            6-digit TOTP code
        """
        if timestamp is None:
            timestamp = int(time.time())

        # Time counter (30-second windows)
        counter = timestamp // TOTP.PERIOD

        # Decode secret
        key = base64.b32decode(secret.upper())

        # HMAC-SHA1
        counter_bytes = counter.to_bytes(8, byteorder='big')
        hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()

        # Dynamic truncation
        offset = hmac_hash[-1] & 0x0F
        code = (
            (hmac_hash[offset] & 0x7F) << 24 |
            (hmac_hash[offset + 1] & 0xFF) << 16 |
            (hmac_hash[offset + 2] & 0xFF) << 8 |
            (hmac_hash[offset + 3] & 0xFF)
        )

        # Return 6-digit code
        return str(code % (10 ** TOTP.DIGITS)).zfill(TOTP.DIGITS)

    @staticmethod
    def verify(secret: str, token: str, tolerance: int = 1) -> bool:
        """
        Verify TOTP token

        Args:
            secret: Base32-encoded secret
            token: Token to verify
            tolerance: Number of periods to check before/after

        Returns:
            True if valid
        """
        timestamp = int(time.time())

        # Check current and adjacent time windows
        for offset in range(-tolerance, tolerance + 1):
            check_time = timestamp + (offset * TOTP.PERIOD)
            if TOTP.get_totp_token(secret, check_time) == token:
                return True

        return False

    @staticmethod
    def get_provisioning_uri(secret: str, username: str, issuer: str = 'CARBS') -> str:
        """
        Generate otpauth:// URI for QR code

        Args:
            secret: TOTP secret
            username: Account name
            issuer: Service name

        Returns:
            otpauth URI for QR code generation
        """
        return (
            f"otpauth://totp/{issuer}:{username}"
            f"?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"
        )


class AuthenticationManager:
    """
    Central authentication manager

    Features:
    - Password authentication with PBKDF2
    - TOTP two-factor authentication
    - JWT session management
    - Brute-force protection
    - IP-based rate limiting
    """

    # Brute-force protection settings
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    LOCKOUT_MULTIPLIER = 2  # Exponential backoff

    # Session settings
    SESSION_DURATION_HOURS = 8
    REFRESH_TOKEN_DAYS = 7

    def __init__(
        self,
        jwt_secret: Optional[str] = None,
        token_blacklist=None,
        session_store=None
    ):
        """
        Initialize authentication manager

        Args:
            jwt_secret: Secret for JWT signing (generated if not provided)
            token_blacklist: Optional TokenBlacklist instance for Redis-backed revocation
            session_store: Optional SessionStore instance for Redis-backed sessions
        """
        self._jwt_secret_file = 'data/.jwt_secret'
        self._jwt_secret = jwt_secret or os.getenv('CARBS_JWT_SECRET')

        if not self._jwt_secret:
            # Try to load persisted JWT secret
            self._jwt_secret = self._load_or_create_jwt_secret()

        self._users: Dict[str, User] = {}
        self._sessions: Dict[str, Session] = {}
        self._ip_attempts: Dict[str, list] = {}  # IP -> list of attempt timestamps

        # Redis-backed token blacklist for immediate revocation
        self._token_blacklist = token_blacklist

        # Redis-backed session store for persistence
        self._session_store = session_store

        # Load users from file if exists
        self._users_file = 'data/.users.json'
        self._load_users()

    def _load_or_create_jwt_secret(self) -> str:
        """
        Load persisted JWT secret or create a new one.
        Ensures JWT secrets persist across restarts.
        """
        os.makedirs(os.path.dirname(self._jwt_secret_file), exist_ok=True)

        if os.path.exists(self._jwt_secret_file):
            try:
                # Read encrypted JWT secret
                with open(self._jwt_secret_file, 'rb') as f:
                    encrypted_data = f.read()

                fernet = Fernet(_get_user_data_key())
                jwt_secret = fernet.decrypt(encrypted_data).decode()
                logger.info("Loaded persisted JWT secret")
                return jwt_secret
            except Exception as e:
                logger.warning(f"Could not load JWT secret: {e}. Generating new one.")

        # Generate new JWT secret and persist it
        jwt_secret = secrets.token_urlsafe(64)

        try:
            fernet = Fernet(_get_user_data_key())
            encrypted_secret = fernet.encrypt(jwt_secret.encode())
            with open(self._jwt_secret_file, 'wb') as f:
                f.write(encrypted_secret)
            os.chmod(self._jwt_secret_file, 0o600)
            logger.info("Generated and persisted new JWT secret")
        except Exception as e:
            logger.warning(f"Could not persist JWT secret: {e}")

        return jwt_secret

    def _load_users(self):
        """Load users from encrypted storage"""
        try:
            if os.path.exists(self._users_file):
                with open(self._users_file, 'rb') as f:
                    encrypted_data = f.read()

                # Decrypt user data
                try:
                    fernet = Fernet(_get_user_data_key())
                    decrypted_data = fernet.decrypt(encrypted_data)
                    data = json.loads(decrypted_data.decode())
                except InvalidToken:
                    # Try loading as legacy unencrypted JSON for migration
                    logger.warning("Attempting legacy unencrypted user data migration...")
                    try:
                        with open(self._users_file, 'r') as f:
                            data = json.load(f)
                        # Will be re-encrypted on next save
                        logger.info("Legacy user data loaded, will be encrypted on next save")
                    except Exception:
                        raise

                for user_data in data:
                    user = User(
                        user_id=user_data['user_id'],
                        username=user_data['username'],
                        password_hash=base64.b64decode(user_data['password_hash']),
                        password_salt=base64.b64decode(user_data['password_salt']),
                        totp_secret=user_data.get('totp_secret'),
                        totp_enabled=user_data.get('totp_enabled', False),
                        role=user_data.get('role', 'viewer'),
                        failed_attempts=user_data.get('failed_attempts', 0),
                        created_at=datetime.fromisoformat(user_data['created_at'])
                    )
                    self._users[user.username] = user
                logger.info(f"Loaded {len(self._users)} users from encrypted storage")
        except Exception as e:
            logger.warning(f"Could not load users: {e}")

    def _save_users(self):
        """Save users to encrypted storage with Fernet encryption"""
        os.makedirs(os.path.dirname(self._users_file), exist_ok=True)
        data = []
        for user in self._users.values():
            data.append({
                'user_id': user.user_id,
                'username': user.username,
                'password_hash': base64.b64encode(user.password_hash).decode(),
                'password_salt': base64.b64encode(user.password_salt).decode(),
                'totp_secret': user.totp_secret,
                'totp_enabled': user.totp_enabled,
                'role': user.role,
                'failed_attempts': user.failed_attempts,
                'created_at': user.created_at.isoformat()
            })

        # Encrypt the user data before writing
        json_data = json.dumps(data).encode()
        fernet = Fernet(_get_user_data_key())
        encrypted_data = fernet.encrypt(json_data)

        with open(self._users_file, 'wb') as f:
            f.write(encrypted_data)
        os.chmod(self._users_file, 0o600)
        logger.debug(f"Saved {len(data)} users to encrypted storage")

    def _hash_password(self, password: str) -> tuple:
        """Hash password with PBKDF2"""
        salt = secrets.token_bytes(32)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480_000,
            backend=default_backend()
        )
        return kdf.derive(password.encode()), salt

    def _verify_password(self, password: str, hash_: bytes, salt: bytes) -> bool:
        """Verify password against hash"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480_000,
            backend=default_backend()
        )
        try:
            kdf.verify(password.encode(), hash_)
            return True
        except Exception:
            return False

    def _check_lockout(self, user: User) -> Optional[str]:
        """Check if user is locked out"""
        if user.locked_until and datetime.now(timezone.utc) < user.locked_until:
            remaining = (user.locked_until - datetime.now(timezone.utc)).seconds // 60
            return f"Account locked. Try again in {remaining} minutes."
        return None

    def _record_failed_attempt(self, user: User):
        """Record failed login attempt and potentially lock account"""
        user.failed_attempts += 1

        if user.failed_attempts >= self.MAX_FAILED_ATTEMPTS:
            # Exponential backoff
            lockout_minutes = self.LOCKOUT_DURATION_MINUTES * (
                self.LOCKOUT_MULTIPLIER ** (user.failed_attempts - self.MAX_FAILED_ATTEMPTS)
            )
            lockout_minutes = min(lockout_minutes, 1440)  # Max 24 hours

            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)
            logger.warning(
                f"User {user.username} locked for {lockout_minutes} minutes "
                f"after {user.failed_attempts} failed attempts"
            )

        self._save_users()

    def _check_ip_rate_limit(self, ip_address: str) -> bool:
        """Check if IP is rate limited"""
        now = time.time()
        window = 300  # 5 minutes
        max_attempts = 20

        if ip_address not in self._ip_attempts:
            self._ip_attempts[ip_address] = []

        # Clean old attempts
        self._ip_attempts[ip_address] = [
            t for t in self._ip_attempts[ip_address]
            if now - t < window
        ]

        if len(self._ip_attempts[ip_address]) >= max_attempts:
            return False

        self._ip_attempts[ip_address].append(now)
        return True

    def create_user(
        self,
        username: str,
        password: str,
        role: str = 'viewer'
    ) -> User:
        """
        Create a new user

        Args:
            username: Unique username
            password: Password (will be hashed)
            role: User role (admin, trader, viewer)

        Returns:
            Created user
        """
        if username in self._users:
            raise AuthError(f"User '{username}' already exists")

        if len(password) < 12:
            raise AuthError("Password must be at least 12 characters")

        password_hash, password_salt = self._hash_password(password)

        user = User(
            user_id=secrets.token_urlsafe(16),
            username=username,
            password_hash=password_hash,
            password_salt=password_salt,
            role=role
        )

        self._users[username] = user
        self._save_users()

        logger.info(f"User '{username}' created with role '{role}'")
        return user

    def setup_totp(self, username: str) -> str:
        """
        Setup TOTP for user

        Args:
            username: Username

        Returns:
            otpauth:// URI for QR code
        """
        if username not in self._users:
            raise AuthError("User not found")

        user = self._users[username]
        user.totp_secret = TOTP.generate_secret()
        self._save_users()

        return TOTP.get_provisioning_uri(user.totp_secret, username)

    def enable_totp(self, username: str, token: str) -> bool:
        """
        Enable TOTP after verifying token

        Args:
            username: Username
            token: TOTP token to verify setup

        Returns:
            True if enabled successfully
        """
        if username not in self._users:
            raise AuthError("User not found")

        user = self._users[username]

        if not user.totp_secret:
            raise AuthError("TOTP not set up. Call setup_totp first.")

        if TOTP.verify(user.totp_secret, token):
            user.totp_enabled = True
            self._save_users()
            logger.info(f"TOTP enabled for user '{username}'")
            return True

        raise AuthError("Invalid TOTP token")

    def authenticate(
        self,
        username: str,
        password: str,
        totp_token: Optional[str] = None,
        ip_address: str = 'unknown',
        user_agent: str = 'unknown'
    ) -> Session:
        """
        Authenticate user and create session

        Args:
            username: Username
            password: Password
            totp_token: TOTP token (required if 2FA enabled)
            ip_address: Client IP for logging
            user_agent: Client user agent

        Returns:
            Session object with JWT token
        """
        # Check IP rate limit
        if not self._check_ip_rate_limit(ip_address):
            raise AuthError("Too many login attempts from this IP. Try again later.")

        # Find user
        user = self._users.get(username)
        if not user:
            # Timing-safe comparison to prevent enumeration
            self._hash_password(password)  # Waste same amount of time
            raise AuthError("Invalid credentials")

        # Check lockout
        lockout_msg = self._check_lockout(user)
        if lockout_msg:
            raise AuthError(lockout_msg)

        # Verify password
        if not self._verify_password(password, user.password_hash, user.password_salt):
            self._record_failed_attempt(user)
            raise AuthError("Invalid credentials")

        # Verify TOTP if enabled
        if user.totp_enabled:
            if not totp_token:
                raise AuthError("TOTP token required")
            if not TOTP.verify(user.totp_secret, totp_token):
                self._record_failed_attempt(user)
                raise AuthError("Invalid TOTP token")

        # Reset failed attempts on successful login
        user.failed_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(timezone.utc)
        self._save_users()

        # Create session
        session = self._create_session(user, ip_address, user_agent)

        logger.info(f"User '{username}' logged in from {ip_address}")
        return session

    def _create_session(
        self,
        user: User,
        ip_address: str,
        user_agent: str
    ) -> Session:
        """Create a new session with JWT tokens"""
        now = datetime.now(timezone.utc)
        session_id = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(64)

        session = Session(
            session_id=session_id,
            user_id=user.user_id,
            username=user.username,
            role=user.role,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=now,
            expires_at=now + timedelta(hours=self.SESSION_DURATION_HOURS),
            refresh_token=refresh_token
        )

        self._sessions[session_id] = session
        return session

    async def _create_session_async(
        self,
        user: User,
        ip_address: str,
        user_agent: str
    ) -> Session:
        """Create a new session with Redis storage"""
        session = self._create_session(user, ip_address, user_agent)

        # Store in Redis if available
        if self._session_store:
            session_data = {
                'session_id': session.session_id,
                'user_id': session.user_id,
                'username': session.username,
                'role': session.role,
                'ip_address': session.ip_address,
                'user_agent': session.user_agent,
                'created_at': session.created_at.isoformat(),
                'expires_at': session.expires_at.isoformat(),
                'refresh_token': session.refresh_token,
                'is_active': session.is_active
            }
            ttl = int((session.expires_at - datetime.now(timezone.utc)).total_seconds())
            await self._session_store.store_session(
                session.session_id,
                session_data,
                ttl_seconds=ttl
            )

        return session

    def create_jwt(self, session: Session) -> str:
        """Create JWT token for session"""
        payload = {
            'session_id': session.session_id,
            'user_id': session.user_id,
            'username': session.username,
            'role': session.role,
            'exp': session.expires_at.timestamp(),
            'iat': session.created_at.timestamp()
        }

        return jwt.encode(payload, self._jwt_secret, algorithm='HS256')

    def verify_jwt(self, token: str) -> Session:
        """
        Verify JWT and return session

        Args:
            token: JWT token

        Returns:
            Valid session

        Raises:
            TokenError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, self._jwt_secret, algorithms=['HS256'])
            session_id = payload.get('session_id')

            if session_id not in self._sessions:
                raise TokenError("Session not found")

            session = self._sessions[session_id]

            if not session.is_active:
                raise TokenError("Session revoked")

            if session.is_expired():
                raise TokenError("Session expired")

            return session

        except jwt.ExpiredSignatureError:
            raise TokenError("Token expired")
        except jwt.InvalidTokenError as e:
            raise TokenError(f"Invalid token: {e}")

    async def verify_jwt_async(self, token: str) -> Session:
        """
        Verify JWT with async blacklist check.

        Use this method when Redis-backed token blacklist is available.

        Args:
            token: JWT token

        Returns:
            Valid session

        Raises:
            TokenError: If token is invalid, expired, or revoked
        """
        try:
            payload = jwt.decode(token, self._jwt_secret, algorithms=['HS256'])
            session_id = payload.get('session_id')

            # Check token blacklist (Redis) for immediate revocation
            if self._token_blacklist:
                if await self._token_blacklist.is_revoked(session_id):
                    raise TokenError("Token has been revoked")

            # Check session store (Redis) first if available
            if self._session_store:
                session_data = await self._session_store.get_session(session_id)
                if session_data:
                    session = Session(
                        session_id=session_data['session_id'],
                        user_id=session_data['user_id'],
                        username=session_data['username'],
                        role=session_data['role'],
                        ip_address=session_data['ip_address'],
                        user_agent=session_data['user_agent'],
                        created_at=datetime.fromisoformat(session_data['created_at']),
                        expires_at=datetime.fromisoformat(session_data['expires_at']),
                        refresh_token=session_data['refresh_token'],
                        is_active=session_data.get('is_active', True)
                    )

                    if not session.is_active:
                        raise TokenError("Session revoked")

                    if session.is_expired():
                        raise TokenError("Session expired")

                    return session

            # Fall back to in-memory sessions
            if session_id not in self._sessions:
                raise TokenError("Session not found")

            session = self._sessions[session_id]

            if not session.is_active:
                raise TokenError("Session revoked")

            if session.is_expired():
                raise TokenError("Session expired")

            return session

        except jwt.ExpiredSignatureError:
            raise TokenError("Token expired")
        except jwt.InvalidTokenError as e:
            raise TokenError(f"Invalid token: {e}")

    def refresh_session(self, refresh_token: str) -> tuple:
        """
        Refresh session using refresh token

        Args:
            refresh_token: Refresh token

        Returns:
            Tuple of (new_jwt, new_refresh_token)
        """
        # Find session by refresh token
        session = None
        for s in self._sessions.values():
            if s.refresh_token == refresh_token:
                session = s
                break

        if not session:
            raise TokenError("Invalid refresh token")

        if not session.is_active:
            raise TokenError("Session revoked")

        # Check refresh token expiry (7 days from session creation)
        refresh_expiry = session.created_at + timedelta(days=self.REFRESH_TOKEN_DAYS)
        if datetime.now(timezone.utc) > refresh_expiry:
            raise TokenError("Refresh token expired")

        # Extend session
        session.expires_at = datetime.now(timezone.utc) + timedelta(hours=self.SESSION_DURATION_HOURS)
        session.refresh_token = secrets.token_urlsafe(64)

        return self.create_jwt(session), session.refresh_token

    def revoke_session(self, session_id: str):
        """Revoke a session (synchronous, in-memory only)"""
        if session_id in self._sessions:
            self._sessions[session_id].is_active = False
            logger.info(f"Session {session_id[:8]}... revoked")

    async def revoke_session_async(self, session_id: str):
        """
        Revoke a session with Redis blacklist support.

        Adds the session to the blacklist for immediate effect across all instances.
        """
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session.is_active = False

            # Calculate remaining TTL for blacklist entry
            remaining_ttl = int((session.expires_at - datetime.now(timezone.utc)).total_seconds())
            remaining_ttl = max(remaining_ttl, 60)  # At least 60 seconds

            # Add to Redis blacklist
            if self._token_blacklist:
                await self._token_blacklist.revoke_token(session_id, remaining_ttl)

            # Remove from Redis session store
            if self._session_store:
                await self._session_store.delete_session(session_id)

            logger.info(f"Session {session_id[:8]}... revoked (blacklist + store)")
        else:
            # Session not in memory, but still blacklist it
            if self._token_blacklist:
                await self._token_blacklist.revoke_token(session_id, 3600)
                logger.info(f"Session {session_id[:8]}... added to blacklist")

    def revoke_all_sessions(self, username: str):
        """Revoke all sessions for a user (synchronous)"""
        count = 0
        for session in self._sessions.values():
            if session.username == username:
                session.is_active = False
                count += 1
        logger.info(f"Revoked {count} sessions for user '{username}'")

    async def revoke_all_sessions_async(self, username: str):
        """
        Revoke all sessions for a user with Redis support.

        Adds all sessions to the blacklist for immediate effect.
        """
        count = 0
        session_ids = []

        for session in self._sessions.values():
            if session.username == username:
                session.is_active = False
                session_ids.append(session.session_id)
                count += 1

        # Add all to blacklist
        if self._token_blacklist and session_ids:
            user = self._users.get(username)
            if user:
                await self._token_blacklist.revoke_all_user_tokens(
                    user.user_id, session_ids, 3600
                )

        # Remove from session store
        if self._session_store:
            for session_id in session_ids:
                await self._session_store.delete_session(session_id)

        logger.info(f"Revoked {count} sessions for user '{username}' (with blacklist)")

    def get_user(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self._users.get(username)

    def list_active_sessions(self, username: Optional[str] = None) -> list:
        """List active sessions, optionally filtered by user"""
        sessions = []
        for session in self._sessions.values():
            if session.is_active and not session.is_expired():
                if username is None or session.username == username:
                    sessions.append(session)
        return sessions


def require_auth(roles: Optional[list] = None):
    """
    Decorator to require authentication for a function

    Args:
        roles: List of allowed roles (None = any authenticated user)

    Usage:
        @require_auth(roles=['admin', 'trader'])
        async def execute_trade(session, ...):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Look for session in kwargs
            session = kwargs.get('session')

            if not session:
                raise AuthError("Authentication required")

            if not isinstance(session, Session):
                raise AuthError("Invalid session")

            if session.is_expired():
                raise AuthError("Session expired")

            if roles and session.role not in roles:
                raise AuthError(f"Insufficient permissions. Required: {roles}")

            return await func(*args, **kwargs)

        return wrapper
    return decorator
