"""Configuration management with validation and error handling"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
import os
import logging
import yaml
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails"""
    pass


class ConfigLoadError(Exception):
    """Raised when configuration file cannot be loaded"""
    pass


@dataclass
class TradingConfig:
    mode: str = "paper"
    min_spread_percent: float = 0.1
    max_spread_percent: float = 5.0
    max_position_usd: float = 1000.0
    max_daily_loss_usd: float = 100.0
    max_daily_trades: int = 20
    order_timeout_seconds: int = 30
    max_slippage_bps: int = 50

    def __post_init__(self):
        """Validate trading config values"""
        if self.mode not in ("paper", "live"):
            raise ConfigValidationError(f"Invalid trading mode: {self.mode}. Must be 'paper' or 'live'")
        if self.min_spread_percent < 0:
            raise ConfigValidationError("min_spread_percent must be non-negative")
        if self.max_spread_percent <= self.min_spread_percent:
            raise ConfigValidationError("max_spread_percent must be greater than min_spread_percent")
        if self.max_position_usd <= 0:
            raise ConfigValidationError("max_position_usd must be positive")
        if self.max_daily_loss_usd <= 0:
            raise ConfigValidationError("max_daily_loss_usd must be positive")
        if self.max_daily_trades <= 0:
            raise ConfigValidationError("max_daily_trades must be positive")
        if self.order_timeout_seconds <= 0:
            raise ConfigValidationError("order_timeout_seconds must be positive")
        if self.max_slippage_bps < 0:
            raise ConfigValidationError("max_slippage_bps must be non-negative")


# Default configurations for optional sections
DEFAULT_MONITORING = {
    "prometheus_port": 9090,
    "healthcheck_interval": 30,
    "metrics_enabled": True
}

DEFAULT_PERFORMANCE = {
    "cache_ttl_seconds": 60,
    "max_concurrent_requests": 10,
    "rate_limit_per_second": 5,
    "check_interval_seconds": 1
}

# Validation bounds for performance parameters
PERFORMANCE_BOUNDS = {
    "cache_ttl_seconds": (1, 3600),  # 1 second to 1 hour
    "max_concurrent_requests": (1, 100),
    "rate_limit_per_second": (1, 100),
    "check_interval_seconds": (0.1, 60)  # Minimum 100ms, max 60 seconds
}

# Validation bounds for monitoring parameters
MONITORING_BOUNDS = {
    "prometheus_port": (1024, 65535),
    "healthcheck_interval": (5, 300)
}

# Validation bounds for risk management parameters
RISK_BOUNDS = {
    "max_drawdown_percent": (1.0, 50.0),
    "position_limit_percent": (1.0, 100.0),
    "correlation_threshold": (0.0, 1.0),
    "var_confidence": (0.9, 0.99)
}

DEFAULT_RISK_MANAGEMENT = {
    "max_drawdown_percent": 10.0,
    "position_limit_percent": 20.0,
    "correlation_threshold": 0.8,
    "var_confidence": 0.95
}

DEFAULT_LOGGING = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "logs/trading.log"
}

DEFAULT_DATABASE = {
    "host": "localhost",
    "port": 5432,
    "name": "trading",
    "pool_size": 5
}

DEFAULT_REDIS = {
    "host": "localhost",
    "port": 6379,
    "db": 0
}


@dataclass
class Config:
    trading: TradingConfig
    exchanges: Dict = field(default_factory=dict)
    symbols: List[str] = field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])
    monitoring: Dict = field(default_factory=lambda: DEFAULT_MONITORING.copy())
    performance: Dict = field(default_factory=lambda: DEFAULT_PERFORMANCE.copy())
    risk_management: Dict = field(default_factory=lambda: DEFAULT_RISK_MANAGEMENT.copy())
    logging: Dict = field(default_factory=lambda: DEFAULT_LOGGING.copy())
    database: Dict = field(default_factory=lambda: DEFAULT_DATABASE.copy())
    redis: Dict = field(default_factory=lambda: DEFAULT_REDIS.copy())

    def __post_init__(self):
        """Validate config after initialization"""
        if not self.exchanges:
            logger.warning("No exchanges configured - trading will be limited")
        if not self.symbols:
            raise ConfigValidationError("At least one trading symbol must be configured")


def _merge_with_defaults(data: Optional[Dict], defaults: Dict) -> Dict:
    """Merge user config with defaults, user values take precedence"""
    if data is None:
        return defaults.copy()
    result = defaults.copy()
    result.update(data)
    return result


def _safe_get(data: Dict, key: str, default: Any = None) -> Any:
    """Safely get a value from dict with default"""
    return data.get(key, default) if data else default


def validate_bounds(data: Dict, bounds: Dict, section_name: str) -> None:
    """
    Validate that numeric values in data fall within specified bounds.

    Args:
        data: Dictionary of config values to validate
        bounds: Dictionary mapping keys to (min, max) tuples
        section_name: Name of config section (for error messages)

    Raises:
        ConfigValidationError: If any value is out of bounds
    """
    if not data:
        return

    for key, (min_val, max_val) in bounds.items():
        if key in data:
            value = data[key]
            if isinstance(value, (int, float)):
                if value < min_val or value > max_val:
                    raise ConfigValidationError(
                        f"{section_name}.{key} must be between {min_val} and {max_val}, got {value}"
                    )


def validate_path_safe(path_value: str, section_name: str) -> None:
    """
    Validate that a path doesn't contain path traversal attempts.

    Args:
        path_value: Path string to validate
        section_name: Name of config section (for error messages)

    Raises:
        ConfigValidationError: If path contains traversal patterns
    """
    if path_value and '..' in path_value:
        raise ConfigValidationError(
            f"{section_name} contains potential path traversal: {path_value}"
        )


def validate_exchange_config(exchanges: Dict) -> None:
    """Validate exchange configuration"""
    if not exchanges:
        return

    required_fields = ["api_key", "api_secret"]

    for name, config in exchanges.items():
        if not isinstance(config, dict):
            raise ConfigValidationError(f"Exchange '{name}' config must be a dictionary")

        # Check for required fields (allow env var placeholders)
        for field in required_fields:
            value = config.get(field, "")
            if not value:
                logger.warning(f"Exchange '{name}' missing {field} - will be disabled")


def load_config(path: str = "config/config.yaml") -> Config:
    """
    Load and validate configuration from YAML file.

    Args:
        path: Path to configuration file

    Returns:
        Validated Config object

    Raises:
        ConfigLoadError: If file cannot be read
        ConfigValidationError: If config values are invalid
    """
    config_path = Path(path)

    # Check file exists
    if not config_path.exists():
        raise ConfigLoadError(f"Configuration file not found: {path}")

    # Check file is readable
    if not os.access(config_path, os.R_OK):
        raise ConfigLoadError(f"Configuration file not readable: {path}")

    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigLoadError(f"Invalid YAML in config file: {e}")
    except IOError as e:
        raise ConfigLoadError(f"Error reading config file: {e}")

    if data is None:
        raise ConfigLoadError("Configuration file is empty")

    if not isinstance(data, dict):
        raise ConfigLoadError("Configuration must be a YAML dictionary")

    # Parse trading config with defaults
    trading_data = _safe_get(data, 'trading', {})
    try:
        trading_config = TradingConfig(**trading_data) if trading_data else TradingConfig()
    except TypeError as e:
        raise ConfigValidationError(f"Invalid trading config: {e}")

    # Validate exchanges
    exchanges = _safe_get(data, 'exchanges', {})
    validate_exchange_config(exchanges)

    # Get merged configs for validation
    monitoring_config = _merge_with_defaults(_safe_get(data, 'monitoring'), DEFAULT_MONITORING)
    performance_config = _merge_with_defaults(_safe_get(data, 'performance'), DEFAULT_PERFORMANCE)
    risk_config = _merge_with_defaults(_safe_get(data, 'risk_management'), DEFAULT_RISK_MANAGEMENT)
    logging_config = _merge_with_defaults(_safe_get(data, 'logging'), DEFAULT_LOGGING)

    # Validate bounds for numeric parameters
    validate_bounds(performance_config, PERFORMANCE_BOUNDS, 'performance')
    validate_bounds(monitoring_config, MONITORING_BOUNDS, 'monitoring')
    validate_bounds(risk_config, RISK_BOUNDS, 'risk_management')

    # Validate path safety for log file
    if 'file' in logging_config:
        validate_path_safe(logging_config['file'], 'logging.file')

    # Build config with defaults for missing sections
    try:
        config = Config(
            trading=trading_config,
            exchanges=exchanges,
            symbols=_safe_get(data, 'symbols', ["BTC/USDT", "ETH/USDT"]),
            monitoring=monitoring_config,
            performance=performance_config,
            risk_management=risk_config,
            logging=logging_config,
            database=_merge_with_defaults(_safe_get(data, 'database'), DEFAULT_DATABASE),
            redis=_merge_with_defaults(_safe_get(data, 'redis'), DEFAULT_REDIS)
        )
    except ConfigValidationError:
        raise
    except Exception as e:
        raise ConfigValidationError(f"Configuration validation failed: {e}")

    logger.info(f"Configuration loaded from {path}")
    return config


def load_config_safe(path: str = "config/config.yaml") -> Optional[Config]:
    """
    Load configuration with graceful error handling.
    Returns None if config cannot be loaded.
    """
    try:
        return load_config(path)
    except (ConfigLoadError, ConfigValidationError) as e:
        logger.error(f"Failed to load configuration: {e}")
        return None


__all__ = [
    'Config',
    'TradingConfig',
    'ConfigValidationError',
    'ConfigLoadError',
    'load_config',
    'load_config_safe'
]
