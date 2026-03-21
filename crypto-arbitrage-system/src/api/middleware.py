"""
API Security Middleware

Implements:
- JWT authentication
- Rate limiting per endpoint
- Request logging
- IP filtering with X-Forwarded-For validation
- CORS controls
- Request size limits
- Request signing verification
"""

import asyncio
import os
import time
import hmac
import hashlib
import logging
import functools
import ipaddress
import threading
from typing import Dict, Optional, Callable, Set, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict

# Import centralized defaults
from ..config.defaults import SECURITY, RATE_LIMIT

logger = logging.getLogger(__name__)


# Trusted proxy networks (configure via environment)
# Default: localhost, Docker networks, common cloud provider ranges
TRUSTED_PROXY_NETWORKS = [
    ipaddress.ip_network('127.0.0.0/8'),      # Localhost
    ipaddress.ip_network('10.0.0.0/8'),       # Private network
    ipaddress.ip_network('172.16.0.0/12'),    # Docker default
    ipaddress.ip_network('192.168.0.0/16'),   # Private network
]


def _load_trusted_proxies() -> List[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Load trusted proxy networks from environment"""
    networks = list(TRUSTED_PROXY_NETWORKS)

    custom_proxies = os.getenv('TRUSTED_PROXIES', '')
    if custom_proxies:
        for proxy in custom_proxies.split(','):
            proxy = proxy.strip()
            if proxy:
                try:
                    networks.append(ipaddress.ip_network(proxy, strict=False))
                except ValueError as e:
                    logger.warning(f"Invalid trusted proxy network '{proxy}': {e}")

    return networks


class TrustedProxyValidator:
    """
    Validates X-Forwarded-For headers to prevent IP spoofing.

    Only trusts X-Forwarded-For if the immediate connection is from a trusted proxy.
    Implements proper header parsing to extract the real client IP.
    """

    def __init__(self, trusted_networks: List = None):
        self.trusted_networks = trusted_networks or _load_trusted_proxies()
        logger.info(f"Loaded {len(self.trusted_networks)} trusted proxy networks")

    def is_trusted_proxy(self, ip: str) -> bool:
        """Check if an IP is from a trusted proxy"""
        try:
            addr = ipaddress.ip_address(ip)
            for network in self.trusted_networks:
                if addr in network:
                    return True
            return False
        except ValueError:
            logger.warning(f"Invalid IP address: {ip}")
            return False

    def get_real_client_ip(
        self,
        direct_ip: str,
        x_forwarded_for: Optional[str] = None,
        x_real_ip: Optional[str] = None
    ) -> str:
        """
        Extract the real client IP from proxy headers.

        Only trusts proxy headers if the direct connection is from a trusted proxy.
        Uses rightmost-untrusted strategy to prevent spoofing.

        Args:
            direct_ip: IP of the direct TCP connection
            x_forwarded_for: X-Forwarded-For header value
            x_real_ip: X-Real-IP header value

        Returns:
            The real client IP address
        """
        # If direct connection is not from a trusted proxy, use direct IP
        if not self.is_trusted_proxy(direct_ip):
            logger.debug(f"Direct IP {direct_ip} not from trusted proxy, using as client IP")
            return direct_ip

        # Parse X-Forwarded-For (format: client, proxy1, proxy2, ...)
        if x_forwarded_for:
            # Split and clean IPs
            forwarded_ips = [ip.strip() for ip in x_forwarded_for.split(',')]

            # Rightmost-untrusted strategy: walk from right to left
            # Stop at the first untrusted IP (that's the real client)
            for ip in reversed(forwarded_ips):
                if ip and not self.is_trusted_proxy(ip):
                    # Validate it's a proper IP address
                    try:
                        ipaddress.ip_address(ip)
                        return ip
                    except ValueError:
                        logger.warning(f"Invalid IP in X-Forwarded-For: {ip}")
                        continue

            # All IPs in chain are trusted, use the leftmost
            if forwarded_ips and forwarded_ips[0]:
                try:
                    ipaddress.ip_address(forwarded_ips[0])
                    return forwarded_ips[0]
                except ValueError:
                    pass

        # Fall back to X-Real-IP if present
        if x_real_ip:
            try:
                ipaddress.ip_address(x_real_ip)
                return x_real_ip
            except ValueError:
                logger.warning(f"Invalid X-Real-IP: {x_real_ip}")

        # Last resort: use direct IP
        return direct_ip


class RequestSigner:
    """
    HMAC-SHA256 request signing for API integrity.

    Prevents request tampering and replay attacks.
    """

    SIGNATURE_HEADER = 'X-CARBS-Signature'
    TIMESTAMP_HEADER = 'X-CARBS-Timestamp'
    NONCE_HEADER = 'X-CARBS-Nonce'

    # Maximum age of a signed request (5 minutes)
    MAX_REQUEST_AGE_SECONDS = 300

    def __init__(self, secret_key: Optional[str] = None):
        self._secret_key = secret_key or os.getenv('CARBS_REQUEST_SIGNING_KEY', '')
        if not self._secret_key:
            logger.warning("No request signing key configured. Request signing disabled.")

        # Nonce cache to prevent replay attacks (store with timestamp for cleanup)
        self._used_nonces: Dict[str, float] = {}
        self._nonce_lock = threading.Lock()  # Thread-safe nonce operations

    def _cleanup_nonces(self):
        """Remove expired nonces (must be called with lock held)"""
        cutoff = time.time() - (self.MAX_REQUEST_AGE_SECONDS * 2)
        self._used_nonces = {
            nonce: ts for nonce, ts in self._used_nonces.items()
            if ts > cutoff
        }

    def sign_request(
        self,
        method: str,
        path: str,
        body: bytes = b'',
        timestamp: Optional[int] = None,
        nonce: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate signature headers for a request.

        Returns:
            Dict with signature headers to add to request
        """
        if not self._secret_key:
            return {}

        import secrets
        timestamp = timestamp or int(time.time())
        nonce = nonce or secrets.token_urlsafe(16)

        # Create signature payload
        payload = f"{method}\n{path}\n{timestamp}\n{nonce}\n".encode() + body

        signature = hmac.new(
            self._secret_key.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return {
            self.SIGNATURE_HEADER: signature,
            self.TIMESTAMP_HEADER: str(timestamp),
            self.NONCE_HEADER: nonce
        }

    def verify_request(
        self,
        method: str,
        path: str,
        body: bytes,
        signature: str,
        timestamp: str,
        nonce: str
    ) -> tuple:
        """
        Verify a signed request.

        Returns:
            (valid: bool, error: Optional[str])
        """
        if not self._secret_key:
            # Signing disabled, accept all requests
            return True, None

        # Check timestamp freshness
        try:
            ts = int(timestamp)
            age = abs(time.time() - ts)
            if age > self.MAX_REQUEST_AGE_SECONDS:
                return False, f"Request too old ({int(age)}s)"
        except ValueError:
            return False, "Invalid timestamp"

        # Verify signature first (before taking lock)
        payload = f"{method}\n{path}\n{timestamp}\n{nonce}\n".encode() + body
        expected = hmac.new(
            self._secret_key.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            return False, "Invalid signature"

        # Check nonce hasn't been used (replay protection) - thread-safe
        with self._nonce_lock:
            self._cleanup_nonces()
            if nonce in self._used_nonces:
                return False, "Nonce already used (replay attack?)"
            # Record nonce as used atomically with check
            self._used_nonces[nonce] = time.time()

        return True, None


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10  # Max requests in 1 second


@dataclass
class RequestContext:
    """Request context for middleware chain"""
    request_id: str
    timestamp: datetime
    ip_address: str
    user_agent: str
    path: str
    method: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None
    authenticated: bool = False


class RateLimiter:
    """
    Token bucket rate limiter with multiple windows

    Prevents abuse while allowing legitimate bursts.
    Supports both IP-based and user-based rate limiting.
    Thread-safe implementation using locking.
    Includes LRU eviction to prevent unbounded memory growth.
    """

    # Maximum unique keys to track (prevents memory exhaustion)
    MAX_TRACKED_KEYS = 10000

    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self._minute_buckets: Dict[str, list] = defaultdict(list)
        self._hour_buckets: Dict[str, list] = defaultdict(list)
        self._second_buckets: Dict[str, list] = defaultdict(list)
        self._last_access: Dict[str, float] = {}  # Track last access for LRU
        self._lock = threading.Lock()  # Thread-safe bucket operations

    def _evict_lru_if_needed(self):
        """Evict least recently used entries if over max capacity."""
        total_keys = len(self._last_access)
        if total_keys > self.MAX_TRACKED_KEYS:
            # Evict oldest 10% of entries
            evict_count = total_keys // 10
            sorted_by_access = sorted(self._last_access.items(), key=lambda x: x[1])
            keys_to_evict = [k for k, _ in sorted_by_access[:evict_count]]

            for key in keys_to_evict:
                self._second_buckets.pop(key, None)
                self._minute_buckets.pop(key, None)
                self._hour_buckets.pop(key, None)
                self._last_access.pop(key, None)

    def _cleanup_bucket(self, bucket: list, window_seconds: int) -> list:
        """Remove old entries from bucket"""
        cutoff = time.time() - window_seconds
        return [t for t in bucket if t > cutoff]

    def check_limit(self, key: str) -> tuple:
        """
        Check if request is within rate limits (thread-safe)

        Args:
            key: Rate limit key (usually IP or user_id)

        Returns:
            (allowed: bool, retry_after: Optional[int])
        """
        now = time.time()

        with self._lock:
            # Clean and check second bucket (burst)
            self._second_buckets[key] = self._cleanup_bucket(
                self._second_buckets[key], 1
            )
            if len(self._second_buckets[key]) >= self.config.burst_limit:
                return False, 1

            # Clean and check minute bucket
            self._minute_buckets[key] = self._cleanup_bucket(
                self._minute_buckets[key], 60
            )
            if len(self._minute_buckets[key]) >= self.config.requests_per_minute:
                oldest = min(self._minute_buckets[key])
                retry_after = max(1, int(60 - (now - oldest)))
                return False, retry_after

            # Clean and check hour bucket
            self._hour_buckets[key] = self._cleanup_bucket(
                self._hour_buckets[key], 3600
            )
            if len(self._hour_buckets[key]) >= self.config.requests_per_hour:
                oldest = min(self._hour_buckets[key])
                retry_after = max(1, int(3600 - (now - oldest)))
                return False, retry_after

            # Record this request atomically with checks
            self._second_buckets[key].append(now)
            self._minute_buckets[key].append(now)
            self._hour_buckets[key].append(now)

            # Update LRU tracking and evict if needed
            self._last_access[key] = now
            self._evict_lru_if_needed()

            return True, None

    def cleanup_old_entries(self):
        """Periodically cleanup old entries to prevent memory bloat"""
        with self._lock:
            for buckets, window in [
                (self._second_buckets, 1),
                (self._minute_buckets, 60),
                (self._hour_buckets, 3600)
            ]:
                keys_to_remove = []
                for key in list(buckets.keys()):  # Create list to avoid dict size change during iteration
                    buckets[key] = self._cleanup_bucket(buckets[key], window)
                    if not buckets[key]:
                        keys_to_remove.append(key)
                for key in keys_to_remove:
                    del buckets[key]


class UserRateLimiter:
    """
    Per-user rate limiter that works alongside IP-based limiting.

    Provides additional protection against authenticated users making
    excessive requests from multiple IPs.
    """

    def __init__(self):
        # Different limits for authenticated users (more generous than IP)
        self._user_configs: Dict[str, RateLimitConfig] = {}
        self._user_limiters: Dict[str, RateLimiter] = {}

        # Default limits for authenticated users
        self._default_config = RateLimitConfig(
            requests_per_minute=120,  # 2x IP limit
            requests_per_hour=2000,   # 2x IP limit
            burst_limit=20            # 2x IP limit
        )

        # Stricter limits for sensitive operations
        self._sensitive_config = RateLimitConfig(
            requests_per_minute=10,
            requests_per_hour=50,
            burst_limit=3
        )

    def get_limiter(self, user_id: str) -> RateLimiter:
        """Get or create rate limiter for a user"""
        if user_id not in self._user_limiters:
            config = self._user_configs.get(user_id, self._default_config)
            self._user_limiters[user_id] = RateLimiter(config)
        return self._user_limiters[user_id]

    def check_limit(self, user_id: str, sensitive: bool = False) -> tuple:
        """
        Check rate limit for an authenticated user.

        Args:
            user_id: The user's ID
            sensitive: If True, use stricter limits for sensitive operations

        Returns:
            (allowed: bool, retry_after: Optional[int])
        """
        if sensitive:
            # Use a separate limiter for sensitive operations
            sensitive_key = f"{user_id}:sensitive"
            if sensitive_key not in self._user_limiters:
                self._user_limiters[sensitive_key] = RateLimiter(self._sensitive_config)
            return self._user_limiters[sensitive_key].check_limit(user_id)

        return self.get_limiter(user_id).check_limit(user_id)

    def set_user_config(self, user_id: str, config: RateLimitConfig):
        """Set custom rate limit config for a specific user"""
        self._user_configs[user_id] = config
        if user_id in self._user_limiters:
            self._user_limiters[user_id] = RateLimiter(config)

    def cleanup(self):
        """Cleanup old entries in all user limiters"""
        for limiter in self._user_limiters.values():
            limiter.cleanup_old_entries()


class SecurityMiddleware:
    """
    Central security middleware for API

    Handles:
    - Authentication verification
    - Rate limiting
    - IP filtering with X-Forwarded-For validation
    - Request logging
    - Security headers
    - Request signature verification
    """

    # Default security headers
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '0',  # Disabled; CSP provides XSS protection. '1; mode=block' is deprecated and unsafe in older IE
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
        'Content-Security-Policy': "default-src 'self'",
        'Cache-Control': 'no-store',
        'Pragma': 'no-cache',
        'X-Permitted-Cross-Domain-Policies': 'none',
        'Referrer-Policy': 'strict-origin-when-cross-origin'
    }

    # Endpoints that don't require authentication
    PUBLIC_ENDPOINTS = {
        '/health',
        '/api/v1/auth/login',
        '/api/v1/auth/refresh'
    }

    # Maximum request body size (1MB)
    MAX_BODY_SIZE = 1024 * 1024

    # Sensitive endpoints that require stricter rate limiting
    SENSITIVE_ENDPOINTS = {
        '/api/v1/trade/execute',
        '/api/v1/emergency/stop',
        '/api/v1/emergency/resume',
        '/api/v1/config/update',
    }

    # Endpoints that require request signing
    SIGNED_ENDPOINTS = {
        '/api/v1/trade/execute',
        '/api/v1/config/update',
        '/api/v1/emergency/stop',
        '/api/v1/emergency/resume',
        '/api/v1/keys/rotate',
    }

    def __init__(
        self,
        auth_manager=None,
        access_control=None,
        audit_logger=None,
        require_signed_requests: bool = None
    ):
        """
        Initialize middleware

        Args:
            auth_manager: Authentication manager instance
            access_control: Access control instance
            audit_logger: Audit logger instance
            require_signed_requests: Require HMAC signatures on sensitive endpoints
        """
        self.auth_manager = auth_manager
        self.access_control = access_control
        self.audit_logger = audit_logger

        self.rate_limiter = RateLimiter()
        self.user_rate_limiter = UserRateLimiter()  # Per-user rate limiting
        self.ip_whitelist: Set[str] = set()
        self.ip_blacklist: Set[str] = set()

        # IP spoofing protection
        self.proxy_validator = TrustedProxyValidator()

        # Request signing
        self.request_signer = RequestSigner()
        self.require_signed_requests = (
            require_signed_requests
            if require_signed_requests is not None
            else os.getenv('REQUIRE_SIGNED_REQUESTS', 'false').lower() == 'true'
        )

        # Per-endpoint rate limiters (persistent instances, not recreated per request)
        self._endpoint_limiters: Dict[str, RateLimiter] = {
            '/api/v1/auth/login': RateLimiter(RateLimitConfig(
                requests_per_minute=5,
                requests_per_hour=20,
                burst_limit=2
            )),
            '/api/v1/trade/execute': RateLimiter(RateLimitConfig(
                requests_per_minute=10,
                requests_per_hour=100,
                burst_limit=3
            )),
        }

    def check_ip_allowed(self, ip_address: str) -> tuple:
        """
        Check if IP is allowed

        Returns:
            (allowed: bool, reason: Optional[str])
        """
        if ip_address in self.ip_blacklist:
            return False, "IP blacklisted"

        if self.ip_whitelist and ip_address not in self.ip_whitelist:
            return False, "IP not in whitelist"

        return True, None

    def check_rate_limit(self, key: str, endpoint: str) -> tuple:
        """
        Check rate limit for key and endpoint

        Returns:
            (allowed: bool, retry_after: Optional[int])
        """
        # Use persistent endpoint-specific limiter if configured
        if endpoint in self._endpoint_limiters:
            limiter = self._endpoint_limiters[endpoint]
        else:
            limiter = self.rate_limiter

        return limiter.check_limit(key)

    def check_user_rate_limit(self, user_id: str, endpoint: str) -> tuple:
        """
        Check rate limit for an authenticated user.

        Applies both IP and user-based rate limiting for defense in depth.

        Args:
            user_id: The authenticated user's ID
            endpoint: The API endpoint being accessed

        Returns:
            (allowed: bool, retry_after: Optional[int])
        """
        is_sensitive = endpoint in self.SENSITIVE_ENDPOINTS
        return self.user_rate_limiter.check_limit(user_id, sensitive=is_sensitive)

    def check_combined_rate_limit(
        self,
        ip_address: str,
        user_id: Optional[str],
        endpoint: str
    ) -> tuple:
        """
        Check both IP and user rate limits.

        Both must pass for the request to be allowed.

        Args:
            ip_address: Client IP address
            user_id: Authenticated user ID (None if not authenticated)
            endpoint: API endpoint being accessed

        Returns:
            (allowed: bool, retry_after: Optional[int], limit_type: str)
        """
        # Check IP rate limit first
        ip_allowed, ip_retry = self.check_rate_limit(ip_address, endpoint)
        if not ip_allowed:
            return False, ip_retry, "ip"

        # Check user rate limit if authenticated
        if user_id:
            user_allowed, user_retry = self.check_user_rate_limit(user_id, endpoint)
            if not user_allowed:
                return False, user_retry, "user"

        return True, None, None

    def verify_token(self, token: str) -> Optional[RequestContext]:
        """
        Verify JWT token and return context

        Args:
            token: JWT token (without Bearer prefix)

        Returns:
            RequestContext with user info, or None if invalid
        """
        if not self.auth_manager:
            return None

        try:
            session = self.auth_manager.verify_jwt(token)
            return RequestContext(
                request_id='',
                timestamp=datetime.now(timezone.utc),
                ip_address='',
                user_agent='',
                path='',
                method='',
                user_id=session.user_id,
                username=session.username,
                role=session.role,
                authenticated=True
            )
        except Exception as e:
            logger.debug(f"Token verification failed: {e}")
            return None

    def log_request(
        self,
        context: RequestContext,
        status_code: int,
        response_time_ms: int
    ):
        """Log request for audit"""
        if self.audit_logger:
            from security.audit import AuditCategory

            self.audit_logger.log(
                category=AuditCategory.ACCESS,
                action=f"{context.method} {context.path}",
                actor=context.username or 'anonymous',
                resource=context.path,
                actor_ip=context.ip_address,
                details={
                    'status_code': status_code,
                    'response_time_ms': response_time_ms,
                    'user_agent': context.user_agent
                },
                success=200 <= status_code < 400
            )

    def get_security_headers(self) -> dict:
        """Get security headers to add to response"""
        return dict(self.SECURITY_HEADERS)

    def is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public (no auth required)"""
        return path in self.PUBLIC_ENDPOINTS

    def get_client_ip(
        self,
        direct_ip: str,
        x_forwarded_for: Optional[str] = None,
        x_real_ip: Optional[str] = None
    ) -> str:
        """
        Get real client IP with X-Forwarded-For validation.

        Only trusts proxy headers from trusted proxy networks.

        Args:
            direct_ip: Direct TCP connection IP
            x_forwarded_for: X-Forwarded-For header value
            x_real_ip: X-Real-IP header value

        Returns:
            Real client IP address
        """
        return self.proxy_validator.get_real_client_ip(
            direct_ip, x_forwarded_for, x_real_ip
        )

    def verify_request_signature(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: Dict[str, str]
    ) -> tuple:
        """
        Verify request signature for sensitive endpoints.

        Args:
            method: HTTP method
            path: Request path
            body: Request body
            headers: Request headers

        Returns:
            (valid: bool, error: Optional[str])
        """
        # Check if signature required for this endpoint
        if path not in self.SIGNED_ENDPOINTS:
            return True, None

        if not self.require_signed_requests:
            return True, None

        signature = headers.get(RequestSigner.SIGNATURE_HEADER)
        timestamp = headers.get(RequestSigner.TIMESTAMP_HEADER)
        nonce = headers.get(RequestSigner.NONCE_HEADER)

        if not all([signature, timestamp, nonce]):
            return False, "Missing signature headers"

        return self.request_signer.verify_request(
            method, path, body, signature, timestamp, nonce
        )


def require_api_auth(required_permission=None):
    """
    Decorator for API endpoints requiring authentication.

    WARNING: This decorator is NOT implemented for FastAPI routes.
    Use FastAPI's Depends(get_current_user) instead.

    This will raise RuntimeError at import time to prevent silent auth bypass.

    Args:
        required_permission: Optional permission to check
    """
    import warnings

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            raise RuntimeError(
                f"require_api_auth decorator on '{func.__name__}' does not enforce authentication. "
                f"Use FastAPI Depends(get_current_user) for auth and check permissions explicitly."
            )
        # Warn at decoration time so usage is caught during testing
        warnings.warn(
            f"require_api_auth on '{func.__name__}' is a no-op. "
            f"Use FastAPI Depends(get_current_user) instead.",
            UserWarning,
            stacklevel=3
        )
        return wrapper
    return decorator


class CORSConfig:
    """
    CORS configuration

    Default: Restrictive (same-origin only)
    """

    def __init__(
        self,
        allow_origins: list = None,
        allow_methods: list = None,
        allow_headers: list = None,
        allow_credentials: bool = False,
        max_age: int = 3600
    ):
        self.allow_origins = allow_origins or []
        self.allow_methods = allow_methods or ['GET', 'POST']
        self.allow_headers = allow_headers or ['Authorization', 'Content-Type']
        self.allow_credentials = allow_credentials
        self.max_age = max_age

    def get_headers(self, origin: str) -> dict:
        """Get CORS headers for response"""
        headers = {}

        if origin in self.allow_origins:
            headers['Access-Control-Allow-Origin'] = origin
        elif '*' in self.allow_origins:
            headers['Access-Control-Allow-Origin'] = '*'

        if self.allow_credentials:
            headers['Access-Control-Allow-Credentials'] = 'true'

        headers['Access-Control-Allow-Methods'] = ', '.join(self.allow_methods)
        headers['Access-Control-Allow-Headers'] = ', '.join(self.allow_headers)
        headers['Access-Control-Max-Age'] = str(self.max_age)

        return headers
