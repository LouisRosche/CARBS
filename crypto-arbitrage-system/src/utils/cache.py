"""Redis cache wrapper with TLS support and proper resource management"""
import asyncio
import json
import os
import ssl
import redis.asyncio as redis
import logging
from decimal import Decimal
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def serialize_value(value):
    """Serialize value to JSON-compatible format"""
    if isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [serialize_value(v) for v in value]
    elif isinstance(value, tuple):
        return [serialize_value(v) for v in value]
    elif isinstance(value, Decimal):
        return str(value)
    elif isinstance(value, datetime):
        return value.isoformat()
    return value


def create_ssl_context(
    ca_cert_path: Optional[str] = None,
    client_cert_path: Optional[str] = None,
    client_key_path: Optional[str] = None,
    verify_mode: str = "required"
) -> ssl.SSLContext:
    """
    Create SSL context for Redis TLS connections.

    Args:
        ca_cert_path: Path to CA certificate file
        client_cert_path: Path to client certificate file (for mutual TLS)
        client_key_path: Path to client key file (for mutual TLS)
        verify_mode: Certificate verification mode ("required", "optional", "none")

    Returns:
        Configured SSL context
    """
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

    # Set verification mode
    if verify_mode == "none":
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    elif verify_mode == "optional":
        context.check_hostname = False
        context.verify_mode = ssl.CERT_OPTIONAL
    else:  # required (default)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

    # Load CA certificate
    if ca_cert_path and os.path.exists(ca_cert_path):
        context.load_verify_locations(ca_cert_path)
        logger.debug(f"Loaded CA certificate from {ca_cert_path}")

    # Load client certificate for mutual TLS
    if client_cert_path and client_key_path:
        if os.path.exists(client_cert_path) and os.path.exists(client_key_path):
            context.load_cert_chain(client_cert_path, client_key_path)
            logger.debug("Loaded client certificate for mutual TLS")

    return context


class RedisCache:
    """
    Redis cache client with TLS/SSL support.

    Supports:
    - Standard Redis connections
    - TLS encrypted connections (rediss://)
    - Mutual TLS authentication
    - Connection pooling
    - Async context manager for guaranteed cleanup
    """

    def __init__(self, config):
        self.config = config
        self.client = None
        self._ssl_context = None
        self._connected = False
        self._shutdown_lock = None  # Will be initialized in connect()

    def _get_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Get or create SSL context if TLS is enabled."""
        use_tls = (
            os.getenv('REDIS_TLS', '').lower() in ('true', '1', 'yes') or
            self.config.get('tls', False)
        )

        if not use_tls:
            return None

        if self._ssl_context:
            return self._ssl_context

        # Get TLS configuration
        ca_cert = os.getenv('REDIS_CA_CERT', self.config.get('ca_cert', ''))
        client_cert = os.getenv('REDIS_CLIENT_CERT', self.config.get('client_cert', ''))
        client_key = os.getenv('REDIS_CLIENT_KEY', self.config.get('client_key', ''))
        verify_mode = os.getenv('REDIS_TLS_VERIFY', self.config.get('tls_verify', 'required'))

        self._ssl_context = create_ssl_context(
            ca_cert_path=ca_cert if ca_cert else None,
            client_cert_path=client_cert if client_cert else None,
            client_key_path=client_key if client_key else None,
            verify_mode=verify_mode
        )

        return self._ssl_context

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected and healthy"""
        return self._connected and self.client is not None

    async def connect(self, max_retries: int = 3, retry_delay: float = 2.0):
        """
        Connect to Redis server with retry logic.

        Automatically uses TLS if REDIS_TLS environment variable is set
        or tls: true is in config.

        Args:
            max_retries: Maximum connection retry attempts
            retry_delay: Delay between retries in seconds
        """
        if self._connected and self.client:
            logger.debug("Redis already connected")
            return

        # Initialize shutdown lock
        if self._shutdown_lock is None:
            self._shutdown_lock = asyncio.Lock()

        host = os.getenv('REDIS_HOST', self.config.get('host', 'localhost'))
        port = int(os.getenv('REDIS_PORT', self.config.get('port', 6379)))
        password = os.getenv('REDIS_PASSWORD', self.config.get('password', ''))

        ssl_context = self._get_ssl_context()

        connection_kwargs = {
            'host': host,
            'port': port,
            'password': password if password else None,
            'decode_responses': True,
            'socket_timeout': self.config.get('socket_timeout', 5),
            'socket_connect_timeout': self.config.get('socket_connect_timeout', 5),
            'max_connections': self.config.get('max_connections', 10),
        }

        if ssl_context:
            connection_kwargs['ssl'] = ssl_context
            logger.info(f"Connecting to Redis with TLS at {host}:{port}")
        else:
            logger.info(f"Connecting to Redis at {host}:{port}")

        last_error = None
        for attempt in range(max_retries):
            try:
                self.client = redis.Redis(**connection_kwargs)

                # Test connection
                await self.client.ping()
                self._connected = True

                if ssl_context:
                    logger.info("Redis cache connected with TLS encryption")
                else:
                    logger.info("Redis cache connected (unencrypted)")
                return

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Redis connection attempt {attempt + 1}/{max_retries} failed: {e}"
                )
                if self.client:
                    try:
                        await self.client.close()
                    except Exception:
                        pass
                    self.client = None

                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))

        logger.error(f"Failed to connect to Redis after {max_retries} attempts: {last_error}")
        raise ConnectionError(f"Failed to connect to Redis: {last_error}")

    async def get(self, key):
        if not self.client:
            return None
        try:
            value = await self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Redis get error for key {key}: {e}")
            return None

    async def set(self, key, value, ttl=None):
        if self.client:
            try:
                serialized = json.dumps(serialize_value(value))
                await self.client.set(key, serialized, ex=ttl)
            except Exception as e:
                logger.warning(f"Redis set error for key {key}: {e}")

    async def delete(self, key):
        """Delete a key from cache"""
        if self.client:
            try:
                await self.client.delete(key)
            except Exception as e:
                logger.warning(f"Redis delete error for key {key}: {e}")

    async def exists(self, key) -> bool:
        """Check if a key exists"""
        if not self.client:
            return False
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.warning(f"Redis exists error for key {key}: {e}")
            return False

    async def close(self):
        """
        Close Redis connection gracefully.

        Thread-safe and idempotent.
        """
        # Handle case where shutdown lock not initialized
        if self._shutdown_lock is None:
            self._shutdown_lock = asyncio.Lock()

        async with self._shutdown_lock:
            if self.client:
                try:
                    await asyncio.wait_for(
                        self.client.close(),
                        timeout=5.0
                    )
                    logger.info("Redis cache connection closed")
                except asyncio.TimeoutError:
                    logger.warning("Redis close timed out")
                except Exception as e:
                    logger.error(f"Error closing Redis connection: {e}")
                finally:
                    self.client = None
                    self._connected = False

    async def health_check(self) -> bool:
        """
        Check Redis connection health.

        Returns:
            True if healthy, False otherwise
        """
        if not self._connected or not self.client:
            return False

        try:
            await self.client.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensures cleanup"""
        await self.close()
        return False  # Don't suppress exceptions

    def __del__(self):
        """Destructor - warn if not properly closed"""
        if self._connected and self.client:
            logger.warning(
                "RedisCache was not properly closed. "
                "Use 'async with' or call close() explicitly."
            )

    async def sadd(self, key: str, *values) -> int:
        """Add values to a set"""
        if not self.client:
            return 0
        try:
            return await self.client.sadd(key, *values)
        except Exception as e:
            logger.warning(f"Redis sadd error for key {key}: {e}")
            return 0

    async def sismember(self, key: str, value: str) -> bool:
        """Check if value is in set"""
        if not self.client:
            return False
        try:
            return await self.client.sismember(key, value)
        except Exception as e:
            logger.warning(f"Redis sismember error for key {key}: {e}")
            return False

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiry on a key"""
        if not self.client:
            return False
        try:
            return await self.client.expire(key, ttl)
        except Exception as e:
            logger.warning(f"Redis expire error for key {key}: {e}")
            return False

    async def hset(self, key: str, field: str, value: str) -> int:
        """Set a hash field"""
        if not self.client:
            return 0
        try:
            return await self.client.hset(key, field, value)
        except Exception as e:
            logger.warning(f"Redis hset error for key {key}: {e}")
            return 0

    async def hget(self, key: str, field: str) -> Optional[str]:
        """Get a hash field"""
        if not self.client:
            return None
        try:
            return await self.client.hget(key, field)
        except Exception as e:
            logger.warning(f"Redis hget error for key {key}: {e}")
            return None

    async def hgetall(self, key: str) -> dict:
        """Get all hash fields"""
        if not self.client:
            return {}
        try:
            return await self.client.hgetall(key)
        except Exception as e:
            logger.warning(f"Redis hgetall error for key {key}: {e}")
            return {}

    async def hdel(self, key: str, *fields) -> int:
        """Delete hash fields"""
        if not self.client:
            return 0
        try:
            return await self.client.hdel(key, *fields)
        except Exception as e:
            logger.warning(f"Redis hdel error for key {key}: {e}")
            return 0


class TokenBlacklist:
    """
    Redis-backed JWT token blacklist for immediate token revocation.

    Uses a set to store revoked token IDs with automatic expiry
    matching the token's remaining lifetime.
    """

    BLACKLIST_KEY = "carbs:token:blacklist"
    SESSION_PREFIX = "carbs:session:"

    def __init__(self, redis_cache: RedisCache):
        self.cache = redis_cache

    async def revoke_token(
        self,
        token_id: str,
        remaining_ttl_seconds: int = 3600
    ) -> bool:
        """
        Add a token to the blacklist.

        Args:
            token_id: The token's unique ID (jti claim or session_id)
            remaining_ttl_seconds: How long to keep in blacklist (match token expiry)

        Returns:
            True if successfully added
        """
        if not self.cache.client:
            logger.warning("Redis not available for token blacklist")
            return False

        try:
            # Use a key per token with expiry
            blacklist_key = f"{self.BLACKLIST_KEY}:{token_id}"
            await self.cache.set(blacklist_key, {"revoked": True}, ttl=remaining_ttl_seconds)
            logger.info(f"Token {token_id[:8]}... added to blacklist")
            return True
        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
            return False

    async def is_revoked(self, token_id: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            token_id: The token's unique ID

        Returns:
            True if token is revoked
        """
        if not self.cache.client:
            # Fail open if Redis unavailable (log warning)
            logger.warning("Redis not available - cannot check token blacklist")
            return False

        try:
            blacklist_key = f"{self.BLACKLIST_KEY}:{token_id}"
            data = await self.cache.get(blacklist_key)
            return data is not None and data.get("revoked", False)
        except Exception as e:
            logger.error(f"Failed to check token blacklist: {e}")
            return False

    async def revoke_all_user_tokens(
        self,
        user_id: str,
        session_ids: list,
        ttl_seconds: int = 3600
    ) -> int:
        """
        Revoke all tokens for a user.

        Args:
            user_id: User whose tokens to revoke
            session_ids: List of session IDs to revoke
            ttl_seconds: TTL for blacklist entries

        Returns:
            Number of tokens revoked
        """
        count = 0
        for session_id in session_ids:
            if await self.revoke_token(session_id, ttl_seconds):
                count += 1

        logger.info(f"Revoked {count} tokens for user {user_id}")
        return count


class SessionStore:
    """
    Redis-backed session storage for persistent sessions.

    Replaces in-memory session storage to survive restarts
    and enable horizontal scaling.
    """

    SESSION_PREFIX = "carbs:session:"
    USER_SESSIONS_PREFIX = "carbs:user_sessions:"

    def __init__(self, redis_cache: RedisCache):
        self.cache = redis_cache

    async def store_session(
        self,
        session_id: str,
        session_data: dict,
        ttl_seconds: int = 28800  # 8 hours default
    ) -> bool:
        """
        Store a session in Redis.

        Args:
            session_id: Unique session identifier
            session_data: Session data dictionary
            ttl_seconds: Session TTL

        Returns:
            True if successfully stored
        """
        if not self.cache.client:
            return False

        try:
            key = f"{self.SESSION_PREFIX}{session_id}"
            await self.cache.set(key, session_data, ttl=ttl_seconds)

            # Also track sessions by user for bulk operations
            user_id = session_data.get('user_id')
            if user_id:
                user_key = f"{self.USER_SESSIONS_PREFIX}{user_id}"
                await self.cache.sadd(user_key, session_id)
                await self.cache.expire(user_key, ttl_seconds)

            return True
        except Exception as e:
            logger.error(f"Failed to store session: {e}")
            return False

    async def get_session(self, session_id: str) -> Optional[dict]:
        """
        Retrieve a session from Redis.

        Args:
            session_id: Session ID to retrieve

        Returns:
            Session data or None if not found
        """
        if not self.cache.client:
            return None

        try:
            key = f"{self.SESSION_PREFIX}{session_id}"
            return await self.cache.get(key)
        except Exception as e:
            logger.error(f"Failed to retrieve session: {e}")
            return None

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session from Redis.

        Args:
            session_id: Session ID to delete

        Returns:
            True if successfully deleted
        """
        if not self.cache.client:
            return False

        try:
            key = f"{self.SESSION_PREFIX}{session_id}"
            await self.cache.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False

    async def get_user_sessions(self, user_id: str) -> list:
        """
        Get all session IDs for a user.

        Args:
            user_id: User ID

        Returns:
            List of session IDs
        """
        if not self.cache.client:
            return []

        try:
            user_key = f"{self.USER_SESSIONS_PREFIX}{user_id}"
            # Get all members of the set
            members = await self.cache.client.smembers(user_key)
            return list(members) if members else []
        except Exception as e:
            logger.error(f"Failed to get user sessions: {e}")
            return []

    async def extend_session(
        self,
        session_id: str,
        new_ttl_seconds: int
    ) -> bool:
        """
        Extend a session's TTL.

        Args:
            session_id: Session to extend
            new_ttl_seconds: New TTL

        Returns:
            True if successful
        """
        if not self.cache.client:
            return False

        try:
            key = f"{self.SESSION_PREFIX}{session_id}"
            return await self.cache.expire(key, new_ttl_seconds)
        except Exception as e:
            logger.error(f"Failed to extend session: {e}")
            return False
