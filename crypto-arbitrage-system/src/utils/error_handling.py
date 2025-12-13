"""
Comprehensive Error Handling and Recovery

Production-grade error management:
- Custom exception hierarchy
- Error classification and categorization
- Automatic recovery strategies
- Error reporting and alerting
- Dead letter queue for failed operations
- Error context preservation

Based on error handling best practices from:
- AWS Builders Library
- Google SRE handbook
- Microsoft Azure reliability patterns
"""

import asyncio
import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Coroutine, Dict, List, Optional, Type, Union
import json
import uuid

logger = logging.getLogger(__name__)


# =============================================================================
# Exception Hierarchy
# =============================================================================

class CARBSException(Exception):
    """Base exception for all CARBS errors"""

    def __init__(
        self,
        message: str,
        code: str = None,
        details: Dict = None,
        recoverable: bool = True,
        original_error: Exception = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code or "CARBS_ERROR"
        self.details = details or {}
        self.recoverable = recoverable
        self.original_error = original_error
        self.timestamp = datetime.now(timezone.utc)
        self.error_id = str(uuid.uuid4())[:8]

    def to_dict(self) -> Dict:
        return {
            "error_id": self.error_id,
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp.isoformat()
        }


# Exchange Errors
class ExchangeError(CARBSException):
    """Base class for exchange-related errors"""

    def __init__(self, exchange: str, message: str, **kwargs):
        self.exchange = exchange
        super().__init__(
            message=f"[{exchange}] {message}",
            code=kwargs.pop("code", "EXCHANGE_ERROR"),
            **kwargs
        )


class ExchangeConnectionError(ExchangeError):
    """Failed to connect to exchange"""

    def __init__(self, exchange: str, message: str = "Connection failed"):
        super().__init__(
            exchange=exchange,
            message=message,
            code="EXCHANGE_CONNECTION_ERROR",
            recoverable=True
        )


class ExchangeAuthenticationError(ExchangeError):
    """Authentication failed with exchange"""

    def __init__(self, exchange: str, message: str = "Authentication failed"):
        super().__init__(
            exchange=exchange,
            message=message,
            code="EXCHANGE_AUTH_ERROR",
            recoverable=False
        )


class ExchangeRateLimitError(ExchangeError):
    """Rate limit exceeded"""

    def __init__(self, exchange: str, retry_after: int = None):
        self.retry_after = retry_after
        super().__init__(
            exchange=exchange,
            message=f"Rate limit exceeded. Retry after {retry_after}s" if retry_after else "Rate limit exceeded",
            code="EXCHANGE_RATE_LIMIT",
            recoverable=True,
            details={"retry_after": retry_after}
        )


class ExchangeAPIError(ExchangeError):
    """API returned an error"""

    def __init__(self, exchange: str, status_code: int, api_message: str):
        self.status_code = status_code
        self.api_message = api_message
        super().__init__(
            exchange=exchange,
            message=f"API error {status_code}: {api_message}",
            code="EXCHANGE_API_ERROR",
            recoverable=status_code >= 500,
            details={"status_code": status_code, "api_message": api_message}
        )


class ExchangeTimeoutError(ExchangeError):
    """Request timed out"""

    def __init__(self, exchange: str, timeout: float):
        super().__init__(
            exchange=exchange,
            message=f"Request timed out after {timeout}s",
            code="EXCHANGE_TIMEOUT",
            recoverable=True,
            details={"timeout": timeout}
        )


# Trading Errors
class TradingError(CARBSException):
    """Base class for trading-related errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            code=kwargs.pop("code", "TRADING_ERROR"),
            **kwargs
        )


class InsufficientBalanceError(TradingError):
    """Insufficient balance for trade"""

    def __init__(self, currency: str, required: float, available: float):
        super().__init__(
            message=f"Insufficient {currency}: need {required}, have {available}",
            code="INSUFFICIENT_BALANCE",
            recoverable=False,
            details={"currency": currency, "required": required, "available": available}
        )


class OrderRejectedError(TradingError):
    """Order was rejected by exchange"""

    def __init__(self, reason: str, order_details: Dict = None):
        super().__init__(
            message=f"Order rejected: {reason}",
            code="ORDER_REJECTED",
            recoverable=False,
            details={"reason": reason, "order": order_details}
        )


class PositionLimitError(TradingError):
    """Position limit exceeded"""

    def __init__(self, symbol: str, current: float, limit: float):
        super().__init__(
            message=f"Position limit exceeded for {symbol}: {current}/{limit}",
            code="POSITION_LIMIT",
            recoverable=False,
            details={"symbol": symbol, "current": current, "limit": limit}
        )


class SlippageExceededError(TradingError):
    """Slippage exceeded maximum allowed"""

    def __init__(self, expected_price: float, actual_price: float, max_slippage: float):
        slippage = abs(actual_price - expected_price) / expected_price * 10000
        super().__init__(
            message=f"Slippage {slippage:.2f} bps exceeded max {max_slippage} bps",
            code="SLIPPAGE_EXCEEDED",
            recoverable=False,
            details={
                "expected_price": expected_price,
                "actual_price": actual_price,
                "slippage_bps": slippage
            }
        )


# Risk Errors
class RiskError(CARBSException):
    """Base class for risk-related errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            code=kwargs.pop("code", "RISK_ERROR"),
            recoverable=False,
            **kwargs
        )


class DrawdownLimitError(RiskError):
    """Drawdown limit exceeded"""

    def __init__(self, current_drawdown: float, max_drawdown: float):
        super().__init__(
            message=f"Drawdown {current_drawdown:.2f}% exceeded limit {max_drawdown:.2f}%",
            code="DRAWDOWN_LIMIT",
            details={"current": current_drawdown, "max": max_drawdown}
        )


class DailyLossLimitError(RiskError):
    """Daily loss limit exceeded"""

    def __init__(self, current_loss: float, limit: float):
        super().__init__(
            message=f"Daily loss ${current_loss:.2f} exceeded limit ${limit:.2f}",
            code="DAILY_LOSS_LIMIT",
            details={"current": current_loss, "limit": limit}
        )


class EmergencyStopError(RiskError):
    """Emergency stop is active"""

    def __init__(self, reason: str):
        super().__init__(
            message=f"Emergency stop active: {reason}",
            code="EMERGENCY_STOP",
            details={"reason": reason}
        )


# System Errors
class SystemError(CARBSException):
    """Base class for system errors"""
    pass


class DatabaseError(SystemError):
    """Database operation failed"""

    def __init__(self, operation: str, message: str):
        super().__init__(
            message=f"Database {operation} failed: {message}",
            code="DATABASE_ERROR",
            recoverable=True
        )


class ConfigurationError(SystemError):
    """Configuration error"""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            code="CONFIG_ERROR",
            recoverable=False
        )


class CircuitBreakerOpenError(SystemError):
    """Circuit breaker is open"""

    def __init__(self, service: str):
        super().__init__(
            message=f"Circuit breaker open for {service}",
            code="CIRCUIT_BREAKER_OPEN",
            recoverable=True
        )


# =============================================================================
# Error Classification
# =============================================================================

class ErrorSeverity(Enum):
    """Error severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for routing and handling"""
    NETWORK = "network"           # Connection, timeout errors
    AUTHENTICATION = "auth"       # API key, permission errors
    RATE_LIMIT = "rate_limit"     # Rate limiting errors
    VALIDATION = "validation"     # Invalid input, parameter errors
    BUSINESS = "business"         # Business logic errors (insufficient funds, etc.)
    RISK = "risk"                 # Risk limit violations
    SYSTEM = "system"             # Internal system errors
    EXTERNAL = "external"         # External service errors
    UNKNOWN = "unknown"


@dataclass
class ClassifiedError:
    """Error with classification metadata"""
    error: Exception
    category: ErrorCategory
    severity: ErrorSeverity
    recoverable: bool
    retry_count: int = 0
    max_retries: int = 3
    context: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def can_retry(self) -> bool:
        return self.recoverable and self.retry_count < self.max_retries


def classify_error(error: Exception) -> ClassifiedError:
    """Classify an exception into category and severity"""

    # Network errors
    if isinstance(error, (ExchangeConnectionError, ExchangeTimeoutError)):
        return ClassifiedError(
            error=error,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.WARNING,
            recoverable=True,
            max_retries=3
        )

    # Authentication errors
    if isinstance(error, ExchangeAuthenticationError):
        return ClassifiedError(
            error=error,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.ERROR,
            recoverable=False
        )

    # Rate limit errors
    if isinstance(error, ExchangeRateLimitError):
        return ClassifiedError(
            error=error,
            category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.WARNING,
            recoverable=True,
            max_retries=5
        )

    # Business/Trading errors
    if isinstance(error, (InsufficientBalanceError, OrderRejectedError, PositionLimitError)):
        return ClassifiedError(
            error=error,
            category=ErrorCategory.BUSINESS,
            severity=ErrorSeverity.WARNING,
            recoverable=False
        )

    # Risk errors
    if isinstance(error, RiskError):
        return ClassifiedError(
            error=error,
            category=ErrorCategory.RISK,
            severity=ErrorSeverity.CRITICAL,
            recoverable=False
        )

    # System errors
    if isinstance(error, (DatabaseError, CircuitBreakerOpenError)):
        return ClassifiedError(
            error=error,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.ERROR,
            recoverable=True,
            max_retries=2
        )

    # Default classification
    return ClassifiedError(
        error=error,
        category=ErrorCategory.UNKNOWN,
        severity=ErrorSeverity.ERROR,
        recoverable=False
    )


# =============================================================================
# Recovery Strategies
# =============================================================================

class RecoveryStrategy(Enum):
    """Recovery strategy types"""
    RETRY = "retry"               # Retry the operation
    RETRY_WITH_BACKOFF = "backoff"  # Retry with exponential backoff
    FALLBACK = "fallback"         # Use fallback value/method
    SKIP = "skip"                 # Skip this operation
    ALERT = "alert"               # Alert and continue
    HALT = "halt"                 # Halt operations
    CIRCUIT_BREAK = "circuit"     # Open circuit breaker


@dataclass
class RecoveryAction:
    """Action to take for recovery"""
    strategy: RecoveryStrategy
    delay_seconds: float = 0
    fallback_value: Any = None
    message: str = ""


class RecoveryManager:
    """
    Manages error recovery strategies

    Determines appropriate recovery action based on:
    - Error type and classification
    - Retry count
    - System state
    - Configuration
    """

    def __init__(self):
        self._recovery_handlers: Dict[ErrorCategory, Callable] = {}
        self._default_strategies: Dict[ErrorCategory, RecoveryStrategy] = {
            ErrorCategory.NETWORK: RecoveryStrategy.RETRY_WITH_BACKOFF,
            ErrorCategory.RATE_LIMIT: RecoveryStrategy.RETRY_WITH_BACKOFF,
            ErrorCategory.AUTHENTICATION: RecoveryStrategy.HALT,
            ErrorCategory.VALIDATION: RecoveryStrategy.SKIP,
            ErrorCategory.BUSINESS: RecoveryStrategy.SKIP,
            ErrorCategory.RISK: RecoveryStrategy.HALT,
            ErrorCategory.SYSTEM: RecoveryStrategy.RETRY,
            ErrorCategory.EXTERNAL: RecoveryStrategy.RETRY_WITH_BACKOFF,
            ErrorCategory.UNKNOWN: RecoveryStrategy.ALERT
        }

    def register_handler(
        self,
        category: ErrorCategory,
        handler: Callable[[ClassifiedError], RecoveryAction]
    ):
        """Register custom recovery handler for category"""
        self._recovery_handlers[category] = handler

    def get_recovery_action(self, classified_error: ClassifiedError) -> RecoveryAction:
        """Get recovery action for classified error"""

        # Check for custom handler
        handler = self._recovery_handlers.get(classified_error.category)
        if handler:
            return handler(classified_error)

        # Use default strategy
        strategy = self._default_strategies.get(
            classified_error.category,
            RecoveryStrategy.ALERT
        )

        # Calculate delay for backoff
        delay = 0
        if strategy == RecoveryStrategy.RETRY_WITH_BACKOFF:
            delay = min(2 ** classified_error.retry_count, 60)  # Max 60 seconds

        # Handle rate limit with specific delay
        if isinstance(classified_error.error, ExchangeRateLimitError):
            if classified_error.error.retry_after:
                delay = classified_error.error.retry_after

        return RecoveryAction(
            strategy=strategy,
            delay_seconds=delay,
            message=f"Recovery: {strategy.value} for {classified_error.category.value}"
        )


# =============================================================================
# Dead Letter Queue
# =============================================================================

@dataclass
class FailedOperation:
    """Record of a failed operation"""
    id: str
    operation: str
    args: tuple
    kwargs: Dict
    error: str
    error_code: str
    timestamp: datetime
    retry_count: int
    context: Dict


class DeadLetterQueue:
    """
    Dead letter queue for failed operations

    Stores operations that failed after all retries for:
    - Manual review
    - Automated reprocessing
    - Analysis
    """

    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._queue: List[FailedOperation] = []
        self._lock = asyncio.Lock()

    async def add(
        self,
        operation: str,
        args: tuple,
        kwargs: Dict,
        error: Exception,
        retry_count: int,
        context: Dict = None
    ):
        """Add failed operation to queue"""
        async with self._lock:
            failed_op = FailedOperation(
                id=str(uuid.uuid4())[:8],
                operation=operation,
                args=args,
                kwargs=kwargs,
                error=str(error),
                error_code=getattr(error, 'code', 'UNKNOWN'),
                timestamp=datetime.now(timezone.utc),
                retry_count=retry_count,
                context=context or {}
            )

            self._queue.append(failed_op)

            # Trim if over max size
            if len(self._queue) > self.max_size:
                self._queue = self._queue[-self.max_size:]

            logger.warning(f"Added to DLQ: {operation} - {error}")

    async def get_pending(self, limit: int = 100) -> List[FailedOperation]:
        """Get pending failed operations"""
        async with self._lock:
            return self._queue[:limit]

    async def remove(self, operation_id: str) -> bool:
        """Remove operation from queue"""
        async with self._lock:
            for i, op in enumerate(self._queue):
                if op.id == operation_id:
                    del self._queue[i]
                    return True
            return False

    async def clear(self):
        """Clear all operations"""
        async with self._lock:
            self._queue.clear()

    @property
    def size(self) -> int:
        return len(self._queue)

    def to_json(self) -> str:
        """Export queue to JSON"""
        return json.dumps(
            [
                {
                    "id": op.id,
                    "operation": op.operation,
                    "error": op.error,
                    "error_code": op.error_code,
                    "timestamp": op.timestamp.isoformat(),
                    "retry_count": op.retry_count
                }
                for op in self._queue
            ],
            indent=2
        )


# =============================================================================
# Error Handler Decorator
# =============================================================================

class ErrorHandler:
    """
    Comprehensive error handler

    Features:
    - Error classification
    - Recovery strategy execution
    - Retry with backoff
    - Dead letter queue
    - Alerting integration
    """

    def __init__(
        self,
        recovery_manager: RecoveryManager = None,
        dlq: DeadLetterQueue = None,
        alert_callback: Callable[[ClassifiedError], Coroutine] = None
    ):
        self.recovery_manager = recovery_manager or RecoveryManager()
        self.dlq = dlq or DeadLetterQueue()
        self.alert_callback = alert_callback

    def __call__(
        self,
        operation_name: str = None,
        max_retries: int = 3,
        reraise: bool = True,
        fallback_value: Any = None
    ) -> Callable:
        """Decorator for error handling"""

        def decorator(func: Callable[..., Coroutine]) -> Callable[..., Coroutine]:
            op_name = operation_name or func.__name__

            @wraps(func)
            async def wrapper(*args, **kwargs) -> Any:
                retry_count = 0

                while True:
                    try:
                        return await func(*args, **kwargs)

                    except Exception as e:
                        # Classify error
                        classified = classify_error(e)
                        classified.retry_count = retry_count
                        classified.max_retries = max_retries
                        classified.context = {
                            "operation": op_name,
                            "args_count": len(args),
                            "kwargs_keys": list(kwargs.keys())
                        }

                        # Log error
                        logger.error(
                            f"Error in {op_name}: {e}",
                            extra={
                                "error_id": getattr(e, 'error_id', 'unknown'),
                                "category": classified.category.value,
                                "retry_count": retry_count
                            }
                        )

                        # Get recovery action
                        action = self.recovery_manager.get_recovery_action(classified)

                        # Execute recovery
                        if action.strategy == RecoveryStrategy.RETRY:
                            if classified.can_retry:
                                retry_count += 1
                                continue

                        elif action.strategy == RecoveryStrategy.RETRY_WITH_BACKOFF:
                            if classified.can_retry:
                                retry_count += 1
                                await asyncio.sleep(action.delay_seconds)
                                continue

                        elif action.strategy == RecoveryStrategy.FALLBACK:
                            return action.fallback_value or fallback_value

                        elif action.strategy == RecoveryStrategy.SKIP:
                            return fallback_value

                        elif action.strategy == RecoveryStrategy.ALERT:
                            if self.alert_callback:
                                await self.alert_callback(classified)

                        # Add to DLQ if exhausted retries
                        if not classified.can_retry:
                            await self.dlq.add(
                                operation=op_name,
                                args=args,
                                kwargs=kwargs,
                                error=e,
                                retry_count=retry_count,
                                context=classified.context
                            )

                        # Alert on critical errors
                        if classified.severity == ErrorSeverity.CRITICAL:
                            if self.alert_callback:
                                await self.alert_callback(classified)

                        # Reraise or return fallback
                        if reraise:
                            raise
                        return fallback_value

            return wrapper
        return decorator


# =============================================================================
# Global Error Handler Instance
# =============================================================================

_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get or create global error handler"""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


def handle_errors(
    operation_name: str = None,
    max_retries: int = 3,
    reraise: bool = True,
    fallback_value: Any = None
) -> Callable:
    """Decorator for error handling using global handler"""
    handler = get_error_handler()
    return handler(
        operation_name=operation_name,
        max_retries=max_retries,
        reraise=reraise,
        fallback_value=fallback_value
    )


__all__ = [
    # Exceptions
    "CARBSException",
    "ExchangeError",
    "ExchangeConnectionError",
    "ExchangeAuthenticationError",
    "ExchangeRateLimitError",
    "ExchangeAPIError",
    "ExchangeTimeoutError",
    "TradingError",
    "InsufficientBalanceError",
    "OrderRejectedError",
    "PositionLimitError",
    "SlippageExceededError",
    "RiskError",
    "DrawdownLimitError",
    "DailyLossLimitError",
    "EmergencyStopError",
    "SystemError",
    "DatabaseError",
    "ConfigurationError",
    "CircuitBreakerOpenError",
    # Classification
    "ErrorSeverity",
    "ErrorCategory",
    "ClassifiedError",
    "classify_error",
    # Recovery
    "RecoveryStrategy",
    "RecoveryAction",
    "RecoveryManager",
    # DLQ
    "FailedOperation",
    "DeadLetterQueue",
    # Handler
    "ErrorHandler",
    "get_error_handler",
    "handle_errors"
]
