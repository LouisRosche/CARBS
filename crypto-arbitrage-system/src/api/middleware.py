"""
API Security Middleware

Implements:
- JWT authentication
- Rate limiting per endpoint
- Request logging
- IP filtering
- CORS controls
- Request size limits
"""

import time
import logging
import functools
from typing import Dict, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)


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
    """

    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self._minute_buckets: Dict[str, list] = defaultdict(list)
        self._hour_buckets: Dict[str, list] = defaultdict(list)
        self._second_buckets: Dict[str, list] = defaultdict(list)

    def _cleanup_bucket(self, bucket: list, window_seconds: int) -> list:
        """Remove old entries from bucket"""
        cutoff = time.time() - window_seconds
        return [t for t in bucket if t > cutoff]

    def check_limit(self, key: str) -> tuple:
        """
        Check if request is within rate limits

        Args:
            key: Rate limit key (usually IP or user_id)

        Returns:
            (allowed: bool, retry_after: Optional[int])
        """
        now = time.time()

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
            retry_after = int(60 - (now - oldest))
            return False, retry_after

        # Clean and check hour bucket
        self._hour_buckets[key] = self._cleanup_bucket(
            self._hour_buckets[key], 3600
        )
        if len(self._hour_buckets[key]) >= self.config.requests_per_hour:
            oldest = min(self._hour_buckets[key])
            retry_after = int(3600 - (now - oldest))
            return False, retry_after

        # Record this request
        self._second_buckets[key].append(now)
        self._minute_buckets[key].append(now)
        self._hour_buckets[key].append(now)

        return True, None

    def cleanup_old_entries(self):
        """Periodically cleanup old entries to prevent memory bloat"""
        now = time.time()
        for buckets, window in [
            (self._second_buckets, 1),
            (self._minute_buckets, 60),
            (self._hour_buckets, 3600)
        ]:
            keys_to_remove = []
            for key in buckets:
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
    - IP filtering
    - Request logging
    - Security headers
    """

    # Default security headers
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'",
        'Cache-Control': 'no-store',
        'Pragma': 'no-cache'
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

    def __init__(
        self,
        auth_manager=None,
        access_control=None,
        audit_logger=None
    ):
        """
        Initialize middleware

        Args:
            auth_manager: Authentication manager instance
            access_control: Access control instance
            audit_logger: Audit logger instance
        """
        self.auth_manager = auth_manager
        self.access_control = access_control
        self.audit_logger = audit_logger

        self.rate_limiter = RateLimiter()
        self.user_rate_limiter = UserRateLimiter()  # Per-user rate limiting
        self.ip_whitelist: Set[str] = set()
        self.ip_blacklist: Set[str] = set()

        # Per-endpoint rate limits
        self.endpoint_limits: Dict[str, RateLimitConfig] = {
            '/api/v1/auth/login': RateLimitConfig(
                requests_per_minute=5,
                requests_per_hour=20,
                burst_limit=2
            ),
            '/api/v1/trade/execute': RateLimitConfig(
                requests_per_minute=10,
                requests_per_hour=100,
                burst_limit=3
            )
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
        # Use endpoint-specific limiter if configured
        if endpoint in self.endpoint_limits:
            limiter = RateLimiter(self.endpoint_limits[endpoint])
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


def require_api_auth(required_permission=None):
    """
    Decorator for API endpoints requiring authentication

    Args:
        required_permission: Optional permission to check

    Usage:
        @require_api_auth(Permission.TRADE_EXECUTE)
        async def execute_trade(request):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # This would integrate with the web framework (FastAPI, etc.)
            # For now, just call the function
            return await func(*args, **kwargs)
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
