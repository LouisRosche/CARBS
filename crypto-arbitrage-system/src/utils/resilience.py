"""
Comprehensive Resilience Patterns

Production-grade resilience implementations:
- Circuit Breaker with sliding window metrics
- Retry with exponential backoff and jitter
- Bulkhead pattern for resource isolation
- Timeout wrapper with cancellation
- Fallback mechanism
- Health monitoring

Based on:
- Netflix Hystrix patterns
- Microsoft Polly library
- AWS Well-Architected resilience pillar
"""

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from functools import wraps
from typing import (
    Any, Callable, Coroutine, Dict, Generic, List, Optional,
    TypeVar, Union
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Failures exceeded threshold, fast-fail all requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5          # Failures before opening
    success_threshold: int = 3          # Successes in half-open before closing
    timeout_seconds: float = 60.0       # Time before attempting half-open
    half_open_max_calls: int = 3        # Max concurrent calls in half-open
    sliding_window_size: int = 10       # Size of sliding window for metrics
    slow_call_duration_threshold: float = 5.0  # Seconds for slow call
    slow_call_rate_threshold: float = 0.5  # Ratio of slow calls to open


@dataclass
class CircuitMetrics:
    """Metrics for circuit breaker monitoring"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    slow_calls: int = 0
    not_permitted_calls: int = 0
    state_transitions: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    current_state: CircuitState = CircuitState.CLOSED

    @property
    def failure_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls

    @property
    def slow_call_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.slow_calls / self.total_calls


class SlidingWindowMetrics:
    """Sliding window for tracking call outcomes"""

    def __init__(self, size: int):
        self.size = size
        self._outcomes: deque = deque(maxlen=size)
        self._durations: deque = deque(maxlen=size)

    def record_success(self, duration: float):
        """Record successful call"""
        self._outcomes.append(True)
        self._durations.append(duration)

    def record_failure(self, duration: float):
        """Record failed call"""
        self._outcomes.append(False)
        self._durations.append(duration)

    def get_failure_rate(self) -> float:
        """Get failure rate from window"""
        if not self._outcomes:
            return 0.0
        failures = sum(1 for o in self._outcomes if not o)
        return failures / len(self._outcomes)

    def get_slow_call_rate(self, threshold: float) -> float:
        """Get ratio of slow calls"""
        if not self._durations:
            return 0.0
        slow_calls = sum(1 for d in self._durations if d >= threshold)
        return slow_calls / len(self._durations)

    def reset(self):
        """Clear the window"""
        self._outcomes.clear()
        self._durations.clear()


class CircuitBreaker:
    """
    Advanced Circuit Breaker with sliding window metrics

    States:
    - CLOSED: Normal operation, monitoring for failures
    - OPEN: Fast-failing all requests after threshold exceeded
    - HALF_OPEN: Testing if service has recovered

    Features:
    - Sliding window failure rate calculation
    - Slow call detection
    - Configurable thresholds
    - Event callbacks for state changes
    - Comprehensive metrics

    Example:
        breaker = CircuitBreaker("exchange_api")

        @breaker
        async def call_exchange():
            return await exchange.get_ticker("BTCUSDT")
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig = None,
        on_state_change: Callable[[CircuitState, CircuitState], None] = None,
        on_failure: Callable[[Exception], None] = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._on_state_change = on_state_change
        self._on_failure = on_failure

        self._state = CircuitState.CLOSED
        self._opened_at: Optional[datetime] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

        self._window = SlidingWindowMetrics(self.config.sliding_window_size)
        self._metrics = CircuitMetrics()

        logger.info(f"Circuit breaker '{name}' initialized with config: "
                   f"failure_threshold={self.config.failure_threshold}, "
                   f"timeout={self.config.timeout_seconds}s")

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def metrics(self) -> CircuitMetrics:
        self._metrics.current_state = self._state
        return self._metrics

    def is_available(self) -> bool:
        """Check if circuit allows calls"""
        if self._state == CircuitState.OPEN:
            return self._should_attempt_reset()
        return True

    def _should_attempt_reset(self) -> bool:
        """Check if timeout has elapsed for half-open transition"""
        if not self._opened_at:
            return True
        elapsed = (datetime.now(timezone.utc) - self._opened_at).total_seconds()
        return elapsed >= self.config.timeout_seconds

    async def _transition_to(self, new_state: CircuitState):
        """Transition to new state with callback"""
        old_state = self._state
        if old_state == new_state:
            return

        self._state = new_state
        self._metrics.state_transitions += 1

        if new_state == CircuitState.OPEN:
            self._opened_at = datetime.now(timezone.utc)
            self._window.reset()
            logger.warning(f"Circuit '{self.name}': {old_state.value} -> OPEN")
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            logger.info(f"Circuit '{self.name}': {old_state.value} -> HALF_OPEN")
        elif new_state == CircuitState.CLOSED:
            self._opened_at = None
            self._window.reset()
            logger.info(f"Circuit '{self.name}': {old_state.value} -> CLOSED")

        if self._on_state_change:
            try:
                self._on_state_change(old_state, new_state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")

    def __call__(self, func: Callable[..., Coroutine]) -> Callable[..., Coroutine]:
        """Decorator to wrap async functions with circuit breaker"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.execute(func, *args, **kwargs)
        return wrapper

    async def execute(
        self,
        func: Callable[..., Coroutine],
        *args,
        **kwargs
    ) -> Any:
        """Execute function with circuit breaker protection"""
        async with self._lock:
            # Check if we can proceed
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    await self._transition_to(CircuitState.HALF_OPEN)
                else:
                    self._metrics.not_permitted_calls += 1
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN"
                    )

            # Check half-open concurrent call limit
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    self._metrics.not_permitted_calls += 1
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' half-open limit reached"
                    )
                self._half_open_calls += 1

        # Execute the function
        start_time = time.monotonic()
        try:
            result = await func(*args, **kwargs)
            duration = time.monotonic() - start_time
            await self._on_success(duration)
            return result

        except Exception as e:
            duration = time.monotonic() - start_time
            await self._on_failure_call(e, duration)
            raise

    async def _on_success(self, duration: float):
        """Handle successful call"""
        async with self._lock:
            self._metrics.total_calls += 1
            self._metrics.successful_calls += 1
            self._metrics.last_success_time = datetime.now(timezone.utc)

            # Track slow calls
            if duration >= self.config.slow_call_duration_threshold:
                self._metrics.slow_calls += 1

            self._window.record_success(duration)

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls -= 1
                # Check if we've had enough successes
                success_count = sum(1 for o in self._window._outcomes if o)
                if success_count >= self.config.success_threshold:
                    await self._transition_to(CircuitState.CLOSED)

    async def _on_failure_call(self, exception: Exception, duration: float):
        """Handle failed call"""
        async with self._lock:
            self._metrics.total_calls += 1
            self._metrics.failed_calls += 1
            self._metrics.last_failure_time = datetime.now(timezone.utc)

            self._window.record_failure(duration)

            if self._on_failure:
                try:
                    self._on_failure(exception)
                except Exception as e:
                    logger.error(f"Error in failure callback: {e}")

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls -= 1
                await self._transition_to(CircuitState.OPEN)

            elif self._state == CircuitState.CLOSED:
                # Check if we should open
                failure_rate = self._window.get_failure_rate()
                slow_call_rate = self._window.get_slow_call_rate(
                    self.config.slow_call_duration_threshold
                )

                if (failure_rate >= self.config.failure_threshold / self.config.sliding_window_size or
                    slow_call_rate >= self.config.slow_call_rate_threshold):
                    await self._transition_to(CircuitState.OPEN)

    def reset(self):
        """Manually reset circuit breaker to closed state"""
        self._state = CircuitState.CLOSED
        self._opened_at = None
        self._half_open_calls = 0
        self._window.reset()
        logger.info(f"Circuit '{self.name}' manually reset to CLOSED")


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


@dataclass
class RetryConfig:
    """Configuration for retry policy"""
    max_attempts: int = 3
    base_delay: float = 1.0              # Base delay in seconds
    max_delay: float = 60.0              # Maximum delay
    exponential_base: float = 2.0        # Exponential backoff base
    jitter: float = 0.1                  # Random jitter factor (0-1)
    retryable_exceptions: tuple = (Exception,)  # Exceptions to retry


class RetryPolicy:
    """
    Retry policy with exponential backoff and jitter

    Implements truncated exponential backoff with decorrelated jitter
    to prevent thundering herd problem.

    Example:
        retry = RetryPolicy(max_attempts=3, base_delay=1.0)

        @retry
        async def flaky_operation():
            return await external_service.call()
    """

    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()

    def __call__(self, func: Callable[..., Coroutine]) -> Callable[..., Coroutine]:
        """Decorator for retry"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.execute(func, *args, **kwargs)
        return wrapper

    async def execute(
        self,
        func: Callable[..., Coroutine],
        *args,
        **kwargs
    ) -> Any:
        """Execute with retry logic"""
        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return await func(*args, **kwargs)

            except self.config.retryable_exceptions as e:
                last_exception = e

                if attempt >= self.config.max_attempts:
                    logger.error(
                        f"Retry exhausted after {attempt} attempts: {e}"
                    )
                    raise

                delay = self._calculate_delay(attempt)
                logger.warning(
                    f"Attempt {attempt} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)

        raise last_exception

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter"""
        # Exponential backoff
        delay = self.config.base_delay * (
            self.config.exponential_base ** (attempt - 1)
        )

        # Cap at max delay
        delay = min(delay, self.config.max_delay)

        # Add jitter (decorrelated)
        jitter_range = delay * self.config.jitter
        delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)


class Bulkhead:
    """
    Bulkhead pattern for resource isolation

    Limits concurrent executions to prevent resource exhaustion
    and isolate failures.

    Example:
        bulkhead = Bulkhead("database", max_concurrent=10, max_wait=5.0)

        @bulkhead
        async def db_query():
            return await db.execute(query)
    """

    def __init__(
        self,
        name: str,
        max_concurrent: int = 10,
        max_wait: float = 10.0
    ):
        self.name = name
        self.max_concurrent = max_concurrent
        self.max_wait = max_wait
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._waiting = 0
        self._active = 0
        self._rejected = 0

    def __call__(self, func: Callable[..., Coroutine]) -> Callable[..., Coroutine]:
        """Decorator for bulkhead"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.execute(func, *args, **kwargs)
        return wrapper

    async def execute(
        self,
        func: Callable[..., Coroutine],
        *args,
        **kwargs
    ) -> Any:
        """Execute with bulkhead protection"""
        self._waiting += 1

        try:
            # Try to acquire with timeout
            acquired = await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.max_wait
            )

            if not acquired:
                self._rejected += 1
                raise BulkheadFullError(
                    f"Bulkhead '{self.name}' is full"
                )

        except asyncio.TimeoutError:
            self._rejected += 1
            raise BulkheadFullError(
                f"Bulkhead '{self.name}' wait timeout exceeded"
            )

        finally:
            self._waiting -= 1

        self._active += 1
        try:
            return await func(*args, **kwargs)
        finally:
            self._active -= 1
            self._semaphore.release()

    @property
    def available_permits(self) -> int:
        return self._semaphore._value

    @property
    def active_calls(self) -> int:
        return self._active

    @property
    def waiting_calls(self) -> int:
        return self._waiting

    @property
    def rejected_calls(self) -> int:
        return self._rejected


class BulkheadFullError(Exception):
    """Raised when bulkhead has no available permits"""
    pass


class Timeout:
    """
    Timeout wrapper with cancellation

    Wraps async calls with a timeout and proper cleanup.

    Example:
        timeout = Timeout(5.0)

        @timeout
        async def slow_operation():
            return await external_call()
    """

    def __init__(
        self,
        duration: float,
        cancel_on_timeout: bool = True
    ):
        self.duration = duration
        self.cancel_on_timeout = cancel_on_timeout

    def __call__(self, func: Callable[..., Coroutine]) -> Callable[..., Coroutine]:
        """Decorator for timeout"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.execute(func, *args, **kwargs)
        return wrapper

    async def execute(
        self,
        func: Callable[..., Coroutine],
        *args,
        **kwargs
    ) -> Any:
        """Execute with timeout"""
        try:
            return await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.duration
            )
        except asyncio.TimeoutError:
            raise TimeoutExceededError(
                f"Operation timed out after {self.duration}s"
            )


class TimeoutExceededError(Exception):
    """Raised when operation exceeds timeout"""
    pass


class Fallback(Generic[T]):
    """
    Fallback mechanism for graceful degradation

    Provides alternative responses when primary operation fails.

    Example:
        fallback = Fallback(fallback_value={"status": "cached"})

        @fallback
        async def get_data():
            return await api.get_data()
    """

    def __init__(
        self,
        fallback_value: T = None,
        fallback_func: Callable[..., Coroutine[Any, Any, T]] = None,
        exceptions: tuple = (Exception,)
    ):
        self.fallback_value = fallback_value
        self.fallback_func = fallback_func
        self.exceptions = exceptions

    def __call__(self, func: Callable[..., Coroutine]) -> Callable[..., Coroutine]:
        """Decorator for fallback"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.execute(func, *args, **kwargs)
        return wrapper

    async def execute(
        self,
        func: Callable[..., Coroutine],
        *args,
        **kwargs
    ) -> T:
        """Execute with fallback"""
        try:
            return await func(*args, **kwargs)
        except self.exceptions as e:
            logger.warning(f"Primary operation failed, using fallback: {e}")

            if self.fallback_func:
                return await self.fallback_func(*args, **kwargs)

            return self.fallback_value


class ResilienceManager:
    """
    Centralized resilience management

    Combines multiple resilience patterns and provides
    unified configuration and monitoring.

    Example:
        manager = ResilienceManager()

        # Register exchange API circuit breakers
        manager.register_circuit_breaker("binance", CircuitBreakerConfig(...))
        manager.register_circuit_breaker("kraken", CircuitBreakerConfig(...))

        # Use in code
        breaker = manager.get_circuit_breaker("binance")

        @breaker
        @manager.get_retry_policy("exchange")
        async def call_binance():
            ...
    """

    def __init__(self):
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._bulkheads: Dict[str, Bulkhead] = {}
        self._retry_policies: Dict[str, RetryPolicy] = {}
        self._health_checks: Dict[str, Callable[[], Coroutine[Any, Any, bool]]] = {}

    def register_circuit_breaker(
        self,
        name: str,
        config: CircuitBreakerConfig = None,
        on_state_change: Callable = None
    ) -> CircuitBreaker:
        """Register and return a circuit breaker"""
        breaker = CircuitBreaker(
            name=name,
            config=config,
            on_state_change=on_state_change
        )
        self._circuit_breakers[name] = breaker
        return breaker

    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name"""
        return self._circuit_breakers.get(name)

    def register_bulkhead(
        self,
        name: str,
        max_concurrent: int = 10,
        max_wait: float = 10.0
    ) -> Bulkhead:
        """Register and return a bulkhead"""
        bulkhead = Bulkhead(
            name=name,
            max_concurrent=max_concurrent,
            max_wait=max_wait
        )
        self._bulkheads[name] = bulkhead
        return bulkhead

    def get_bulkhead(self, name: str) -> Optional[Bulkhead]:
        """Get bulkhead by name"""
        return self._bulkheads.get(name)

    def register_retry_policy(
        self,
        name: str,
        config: RetryConfig = None
    ) -> RetryPolicy:
        """Register and return a retry policy"""
        policy = RetryPolicy(config=config)
        self._retry_policies[name] = policy
        return policy

    def get_retry_policy(self, name: str) -> Optional[RetryPolicy]:
        """Get retry policy by name"""
        return self._retry_policies.get(name)

    def register_health_check(
        self,
        name: str,
        check: Callable[[], Coroutine[Any, Any, bool]]
    ):
        """Register a health check function"""
        self._health_checks[name] = check

    async def run_health_checks(self) -> Dict[str, bool]:
        """Run all registered health checks"""
        results = {}

        for name, check in self._health_checks.items():
            try:
                results[name] = await asyncio.wait_for(check(), timeout=10.0)
            except Exception as e:
                logger.error(f"Health check '{name}' failed: {e}")
                results[name] = False

        return results

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics from all components"""
        metrics = {
            "circuit_breakers": {},
            "bulkheads": {}
        }

        for name, breaker in self._circuit_breakers.items():
            m = breaker.metrics
            metrics["circuit_breakers"][name] = {
                "state": m.current_state.value,
                "total_calls": m.total_calls,
                "failure_rate": m.failure_rate,
                "slow_call_rate": m.slow_call_rate,
                "state_transitions": m.state_transitions
            }

        for name, bulkhead in self._bulkheads.items():
            metrics["bulkheads"][name] = {
                "active_calls": bulkhead.active_calls,
                "waiting_calls": bulkhead.waiting_calls,
                "rejected_calls": bulkhead.rejected_calls,
                "available_permits": bulkhead.available_permits
            }

        return metrics


# Convenience function to combine patterns
def with_resilience(
    circuit_breaker: CircuitBreaker = None,
    retry: RetryPolicy = None,
    bulkhead: Bulkhead = None,
    timeout: Timeout = None,
    fallback: Fallback = None
) -> Callable:
    """
    Combine multiple resilience patterns

    Order of execution (outer to inner):
    1. Fallback (catches all failures)
    2. Timeout (wraps everything)
    3. Circuit Breaker (fast-fail)
    4. Bulkhead (limit concurrency)
    5. Retry (retry failures)
    6. Actual function

    Example:
        @with_resilience(
            circuit_breaker=breaker,
            retry=RetryPolicy(),
            timeout=Timeout(10.0),
            fallback=Fallback(fallback_value=[])
        )
        async def get_data():
            return await api.fetch()
    """
    def decorator(func: Callable[..., Coroutine]) -> Callable[..., Coroutine]:
        wrapped = func

        # Apply in reverse order (innermost first)
        if retry:
            wrapped = retry(wrapped)

        if bulkhead:
            wrapped = bulkhead(wrapped)

        if circuit_breaker:
            wrapped = circuit_breaker(wrapped)

        if timeout:
            wrapped = timeout(wrapped)

        if fallback:
            wrapped = fallback(wrapped)

        return wrapped

    return decorator


__all__ = [
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitMetrics",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "RetryConfig",
    "RetryPolicy",
    "Bulkhead",
    "BulkheadFullError",
    "Timeout",
    "TimeoutExceededError",
    "Fallback",
    "ResilienceManager",
    "with_resilience"
]
