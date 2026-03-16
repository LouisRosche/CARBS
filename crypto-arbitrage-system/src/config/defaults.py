"""
Centralized system defaults and constants.

All hardcoded defaults should be defined here to enable:
- Easy auditing of system parameters
- Consistent configuration across components
- Override via configuration files
- Clear documentation of parameter meanings

Organized by subsystem for maintainability.
"""
from dataclasses import dataclass
from typing import Dict, Any
from decimal import Decimal


# =============================================================================
# DATABASE DEFAULTS
# =============================================================================

@dataclass(frozen=True)
class DatabaseDefaults:
    """Default values for database configuration"""
    HOST: str = "localhost"
    PORT: int = 5432
    DATABASE: str = "arbitrage"
    USER: str = "arbitrage_user"
    PASSWORD: str = ""

    # Connection pool settings
    POOL_MIN_SIZE: int = 2
    POOL_MAX_SIZE: int = 10
    COMMAND_TIMEOUT: int = 60  # seconds
    CONNECT_TIMEOUT: int = 30  # seconds
    MAX_CONNECT_RETRIES: int = 3
    CONNECT_RETRY_DELAY: float = 2.0  # seconds


DATABASE = DatabaseDefaults()


# =============================================================================
# REDIS DEFAULTS
# =============================================================================

@dataclass(frozen=True)
class RedisDefaults:
    """Default values for Redis configuration"""
    HOST: str = "localhost"
    PORT: int = 6379
    DB: int = 0
    PASSWORD: str = ""

    # Connection settings
    SOCKET_TIMEOUT: int = 5  # seconds
    SOCKET_CONNECT_TIMEOUT: int = 5  # seconds
    MAX_CONNECTIONS: int = 10
    MAX_CONNECT_RETRIES: int = 3
    CONNECT_RETRY_DELAY: float = 2.0  # seconds

    # TLS settings
    TLS_ENABLED: bool = False
    TLS_VERIFY: str = "required"  # required, optional, none

    # Cache TTLs
    DEFAULT_TTL: int = 3600  # 1 hour
    SHORT_TTL: int = 60  # 1 minute
    LONG_TTL: int = 86400  # 24 hours


REDIS = RedisDefaults()


# =============================================================================
# TRADING DEFAULTS
# =============================================================================

@dataclass(frozen=True)
class TradingDefaults:
    """Default values for trading configuration"""
    MODE: str = "paper"

    # Spread thresholds (percentage)
    MIN_SPREAD_PERCENT: float = 0.1
    MAX_SPREAD_PERCENT: float = 5.0

    # Position limits
    MAX_POSITION_USD: float = 1000.0
    MAX_DAILY_LOSS_USD: float = 100.0
    MAX_DAILY_TRADES: int = 20

    # Execution settings
    ORDER_TIMEOUT_SECONDS: int = 30
    MAX_SLIPPAGE_BPS: int = 50  # basis points

    # Trade amount validation
    MIN_TRADE_AMOUNT: Decimal = Decimal('0.00000001')  # 1 satoshi equivalent
    MAX_TRADE_AMOUNT: Decimal = Decimal('1000000')

    # Price validation
    MIN_PRICE: Decimal = Decimal('0.00000001')
    MAX_PRICE: Decimal = Decimal('10000000')


TRADING = TradingDefaults()


# =============================================================================
# RATE LIMITING DEFAULTS
# =============================================================================

@dataclass(frozen=True)
class RateLimitDefaults:
    """Default values for rate limiting"""
    # API rate limits (per time window)
    REQUESTS_PER_SECOND: int = 10
    REQUESTS_PER_MINUTE: int = 100
    REQUESTS_PER_HOUR: int = 1000

    # Token bucket settings
    BUCKET_SIZE: int = 100
    REFILL_RATE: float = 1.67  # tokens per second

    # Cleanup intervals
    BUCKET_CLEANUP_INTERVAL: int = 60  # seconds
    NONCE_EXPIRY_SECONDS: int = 300  # 5 minutes


RATE_LIMIT = RateLimitDefaults()


# =============================================================================
# SECURITY DEFAULTS
# =============================================================================

@dataclass(frozen=True)
class SecurityDefaults:
    """Default values for security settings"""
    # JWT settings
    JWT_EXPIRY_SECONDS: int = 28800  # 8 hours
    JWT_REFRESH_THRESHOLD: int = 1800  # 30 minutes before expiry

    # Session settings
    SESSION_TIMEOUT_SECONDS: int = 28800  # 8 hours
    MAX_SESSIONS_PER_USER: int = 5

    # Password requirements
    MIN_PASSWORD_LENGTH: int = 12
    REQUIRE_UPPERCASE: bool = True
    REQUIRE_LOWERCASE: bool = True
    REQUIRE_DIGITS: bool = True
    REQUIRE_SPECIAL: bool = True

    # Nonce settings
    NONCE_WINDOW_SECONDS: int = 300  # 5 minutes
    MAX_NONCE_CACHE_SIZE: int = 10000

    # IP spoofing protection
    TRUSTED_PROXIES: tuple = ("127.0.0.1", "::1")
    MAX_FORWARDED_HEADERS: int = 5

    # Request signing
    SIGNATURE_EXPIRY_SECONDS: int = 300  # 5 minutes
    SIGNATURE_ALGORITHM: str = "hmac-sha256"


SECURITY = SecurityDefaults()


# =============================================================================
# CIRCUIT BREAKER DEFAULTS
# =============================================================================

@dataclass(frozen=True)
class CircuitBreakerDefaults:
    """Default values for circuit breaker pattern"""
    FAILURE_THRESHOLD: int = 5
    SUCCESS_THRESHOLD: int = 2
    TIMEOUT_SECONDS: int = 60
    HALF_OPEN_MAX_CALLS: int = 3

    # Sliding window settings
    WINDOW_SIZE: int = 10
    MIN_CALLS_FOR_THRESHOLD: int = 5


CIRCUIT_BREAKER = CircuitBreakerDefaults()


# =============================================================================
# RETRY DEFAULTS
# =============================================================================

@dataclass(frozen=True)
class RetryDefaults:
    """Default values for retry logic"""
    MAX_RETRIES: int = 3
    BASE_BACKOFF_SECONDS: float = 2.0
    MAX_BACKOFF_SECONDS: float = 60.0
    BACKOFF_MULTIPLIER: float = 2.0

    # Jitter settings (decorrelated jitter)
    JITTER_ENABLED: bool = True
    JITTER_FACTOR: float = 0.5


RETRY = RetryDefaults()


# =============================================================================
# WEBSOCKET DEFAULTS
# =============================================================================

@dataclass(frozen=True)
class WebSocketDefaults:
    """Default values for WebSocket connections"""
    PING_INTERVAL_SECONDS: int = 30
    PONG_TIMEOUT_SECONDS: int = 10
    RECONNECT_DELAY_SECONDS: float = 5.0
    MAX_RECONNECT_ATTEMPTS: int = 10
    MAX_MESSAGE_SIZE: int = 1048576  # 1MB

    # Heartbeat settings
    HEARTBEAT_INTERVAL: int = 15  # seconds
    HEARTBEAT_TIMEOUT: int = 30  # seconds


WEBSOCKET = WebSocketDefaults()


# =============================================================================
# MONITORING DEFAULTS
# =============================================================================

@dataclass(frozen=True)
class MonitoringDefaults:
    """Default values for monitoring configuration"""
    PROMETHEUS_PORT: int = 9090
    HEALTHCHECK_INTERVAL: int = 30  # seconds
    METRICS_ENABLED: bool = True

    # Health check thresholds
    MEMORY_THRESHOLD_PERCENT: float = 90.0
    DISK_THRESHOLD_PERCENT: float = 85.0
    CPU_THRESHOLD_PERCENT: float = 95.0

    # Metric collection
    METRIC_RETENTION_HOURS: int = 24
    METRIC_AGGREGATION_SECONDS: int = 60


MONITORING = MonitoringDefaults()


# =============================================================================
# NOTIFICATION DEFAULTS
# =============================================================================

@dataclass(frozen=True)
class NotificationDefaults:
    """Default values for notification system"""
    # Rate limiting
    MIN_INTERVAL_SECONDS: int = 60  # Minimum time between same notifications
    DEDUPLICATION_WINDOW_SECONDS: int = 300  # 5 minutes

    # Batch settings
    BATCH_SIZE: int = 10
    BATCH_TIMEOUT_SECONDS: int = 5

    # Channel timeouts
    EMAIL_TIMEOUT: int = 30
    SLACK_TIMEOUT: int = 10
    DISCORD_TIMEOUT: int = 10
    WEBHOOK_TIMEOUT: int = 10
    PAGERDUTY_TIMEOUT: int = 10


NOTIFICATION = NotificationDefaults()


# =============================================================================
# RISK MANAGEMENT DEFAULTS
# =============================================================================

@dataclass(frozen=True)
class RiskDefaults:
    """Default values for risk management"""
    MAX_DRAWDOWN_PERCENT: float = 10.0
    POSITION_LIMIT_PERCENT: float = 20.0
    CORRELATION_THRESHOLD: float = 0.8
    VAR_CONFIDENCE: float = 0.95

    # Daily limits
    MAX_DAILY_LOSS_PERCENT: float = 5.0
    MAX_DAILY_VOLUME_PERCENT: float = 25.0

    # Position sizing
    MIN_POSITION_SIZE_USD: float = 10.0
    DEFAULT_LEVERAGE: float = 1.0
    MAX_LEVERAGE: float = 3.0

    # Kelly Criterion
    KELLY_MAX_FRACTION: float = 0.10  # Maximum Kelly fraction (10% of capital)
    KELLY_SAFETY_FACTOR: float = 0.25  # Safety factor applied to raw Kelly (quarter-Kelly)


RISK = RiskDefaults()


# =============================================================================
# LOGGING DEFAULTS
# =============================================================================

@dataclass(frozen=True)
class LoggingDefaults:
    """Default values for logging configuration"""
    LEVEL: str = "INFO"
    FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    FILE: str = "logs/trading.log"

    # Rotation settings
    MAX_FILE_SIZE_MB: int = 100
    BACKUP_COUNT: int = 10

    # Audit log settings
    AUDIT_RETENTION_DAYS: int = 90
    AUDIT_ROTATION_DAYS: int = 7


LOGGING = LoggingDefaults()


# =============================================================================
# EXCHANGE-SPECIFIC DEFAULTS
# =============================================================================

@dataclass(frozen=True)
class ExchangeDefaults:
    """Default values for exchange connections"""
    # Rate limits (per exchange typical defaults)
    BINANCE_RATE_LIMIT: int = 1200  # requests per minute
    KUCOIN_RATE_LIMIT: int = 1800  # requests per minute
    MEXC_RATE_LIMIT: int = 1000  # requests per minute

    # Timeout settings
    REQUEST_TIMEOUT: int = 30  # seconds
    ORDER_TIMEOUT: int = 60  # seconds

    # Fees (conservative defaults)
    DEFAULT_TAKER_FEE: float = 0.001  # 0.1%
    DEFAULT_MAKER_FEE: float = 0.001  # 0.1%


EXCHANGE = ExchangeDefaults()


# =============================================================================
# PERFORMANCE DEFAULTS
# =============================================================================

@dataclass(frozen=True)
class PerformanceDefaults:
    """Default values for performance tuning"""
    CACHE_TTL_SECONDS: int = 60
    MAX_CONCURRENT_REQUESTS: int = 10
    RATE_LIMIT_PER_SECOND: int = 5
    CHECK_INTERVAL_SECONDS: float = 1.0

    # Thread pool settings
    THREAD_POOL_SIZE: int = 4
    MAX_QUEUE_SIZE: int = 1000

    # Async settings
    ASYNC_TIMEOUT_SECONDS: int = 30


PERFORMANCE = PerformanceDefaults()


# =============================================================================
# APPROVAL WORKFLOW DEFAULTS
# =============================================================================

@dataclass(frozen=True)
class ApprovalDefaults:
    """Default values for approval workflow"""
    REQUEST_EXPIRY_SECONDS: int = 86400  # 24 hours
    MIN_APPROVERS: int = 1
    MAX_PENDING_REQUESTS: int = 100
    CLEANUP_INTERVAL_SECONDS: int = 3600  # 1 hour


APPROVAL = ApprovalDefaults()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_all_defaults() -> Dict[str, Any]:
    """Get all default values as a dictionary for configuration merging"""
    return {
        'database': {
            'host': DATABASE.HOST,
            'port': DATABASE.PORT,
            'database': DATABASE.DATABASE,
            'user': DATABASE.USER,
            'pool_min_size': DATABASE.POOL_MIN_SIZE,
            'pool_max_size': DATABASE.POOL_MAX_SIZE,
            'command_timeout': DATABASE.COMMAND_TIMEOUT,
            'connect_timeout': DATABASE.CONNECT_TIMEOUT,
            'max_connect_retries': DATABASE.MAX_CONNECT_RETRIES,
        },
        'redis': {
            'host': REDIS.HOST,
            'port': REDIS.PORT,
            'db': REDIS.DB,
            'socket_timeout': REDIS.SOCKET_TIMEOUT,
            'socket_connect_timeout': REDIS.SOCKET_CONNECT_TIMEOUT,
            'max_connections': REDIS.MAX_CONNECTIONS,
            'tls': REDIS.TLS_ENABLED,
        },
        'trading': {
            'mode': TRADING.MODE,
            'min_spread_percent': TRADING.MIN_SPREAD_PERCENT,
            'max_spread_percent': TRADING.MAX_SPREAD_PERCENT,
            'max_position_usd': TRADING.MAX_POSITION_USD,
            'max_daily_loss_usd': TRADING.MAX_DAILY_LOSS_USD,
            'max_daily_trades': TRADING.MAX_DAILY_TRADES,
            'order_timeout_seconds': TRADING.ORDER_TIMEOUT_SECONDS,
            'max_slippage_bps': TRADING.MAX_SLIPPAGE_BPS,
        },
        'security': {
            'jwt_expiry_seconds': SECURITY.JWT_EXPIRY_SECONDS,
            'session_timeout_seconds': SECURITY.SESSION_TIMEOUT_SECONDS,
            'max_sessions_per_user': SECURITY.MAX_SESSIONS_PER_USER,
            'nonce_window_seconds': SECURITY.NONCE_WINDOW_SECONDS,
        },
        'circuit_breaker': {
            'failure_threshold': CIRCUIT_BREAKER.FAILURE_THRESHOLD,
            'success_threshold': CIRCUIT_BREAKER.SUCCESS_THRESHOLD,
            'timeout_seconds': CIRCUIT_BREAKER.TIMEOUT_SECONDS,
        },
        'retry': {
            'max_retries': RETRY.MAX_RETRIES,
            'base_backoff_seconds': RETRY.BASE_BACKOFF_SECONDS,
            'max_backoff_seconds': RETRY.MAX_BACKOFF_SECONDS,
        },
        'monitoring': {
            'prometheus_port': MONITORING.PROMETHEUS_PORT,
            'healthcheck_interval': MONITORING.HEALTHCHECK_INTERVAL,
            'metrics_enabled': MONITORING.METRICS_ENABLED,
            'memory_threshold_percent': MONITORING.MEMORY_THRESHOLD_PERCENT,
            'disk_threshold_percent': MONITORING.DISK_THRESHOLD_PERCENT,
        },
        'notification': {
            'min_interval_seconds': NOTIFICATION.MIN_INTERVAL_SECONDS,
            'deduplication_window_seconds': NOTIFICATION.DEDUPLICATION_WINDOW_SECONDS,
        },
        'risk': {
            'max_drawdown_percent': RISK.MAX_DRAWDOWN_PERCENT,
            'position_limit_percent': RISK.POSITION_LIMIT_PERCENT,
            'var_confidence': RISK.VAR_CONFIDENCE,
            'kelly_max_fraction': RISK.KELLY_MAX_FRACTION,
            'kelly_safety_factor': RISK.KELLY_SAFETY_FACTOR,
        },
        'logging': {
            'level': LOGGING.LEVEL,
            'format': LOGGING.FORMAT,
            'file': LOGGING.FILE,
        },
        'performance': {
            'cache_ttl_seconds': PERFORMANCE.CACHE_TTL_SECONDS,
            'max_concurrent_requests': PERFORMANCE.MAX_CONCURRENT_REQUESTS,
            'rate_limit_per_second': PERFORMANCE.RATE_LIMIT_PER_SECOND,
            'check_interval_seconds': PERFORMANCE.CHECK_INTERVAL_SECONDS,
        },
    }


__all__ = [
    'DATABASE', 'REDIS', 'TRADING', 'RATE_LIMIT', 'SECURITY',
    'CIRCUIT_BREAKER', 'RETRY', 'WEBSOCKET', 'MONITORING',
    'NOTIFICATION', 'RISK', 'LOGGING', 'EXCHANGE', 'PERFORMANCE',
    'APPROVAL', 'get_all_defaults',
]
