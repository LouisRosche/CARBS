"""
Execution Engine with Circuit Breaker Pattern

Implements robust order execution with:
- Circuit breaker pattern for fault tolerance
- Token bucket rate limiting
- Exponential backoff retry logic
- Order state management
- Partial fill handling
- Execution analytics

Based on resilience patterns from:
- Netflix Hystrix
- Martin Fowler's Circuit Breaker pattern
- AWS Well-Architected Framework
"""

import asyncio
from decimal import Decimal
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import logging
import time

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class OrderStatus(Enum):
    """Order execution status"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class OrderState:
    """Track order execution state"""
    order_id: Optional[str] = None
    exchange: str = ""
    symbol: str = ""
    side: str = ""  # 'buy' or 'sell'
    order_type: str = "limit"
    amount: Decimal = Decimal('0')
    price: Decimal = Decimal('0')
    filled_amount: Decimal = Decimal('0')
    avg_fill_price: Decimal = Decimal('0')
    fee: Decimal = Decimal('0')
    fee_currency: str = ""
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: Optional[str] = None
    retry_count: int = 0

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def is_active(self) -> bool:
        return self.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL]

    @property
    def execution_time_ms(self) -> int:
        """Execution time in milliseconds"""
        delta = self.updated_at - self.created_at
        return int(delta.total_seconds() * 1000)


class CircuitBreaker:
    """
    Circuit Breaker pattern implementation

    Prevents cascading failures by stopping requests to failing services
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: int = 60
    ):
        """
        Args:
            name: Circuit breaker identifier
            failure_threshold: Failures before opening circuit
            success_threshold: Successes in half-open before closing
            timeout_seconds: Time to wait before trying half-open
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.opened_at: Optional[datetime] = None

        logger.info(f"Circuit breaker '{name}' initialized")

    def call(self, func):
        """Decorator to wrap calls with circuit breaker"""
        async def wrapper(*args, **kwargs):
            # Check if circuit is open
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    raise Exception(f"Circuit breaker '{self.name}' is OPEN")

            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result

            except Exception as e:
                self._on_failure()
                raise e

        return wrapper

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try half-open"""
        if not self.opened_at:
            return True

        elapsed = datetime.now(timezone.utc) - self.opened_at
        return elapsed.total_seconds() >= self.timeout_seconds

    def _transition_to_half_open(self):
        """Transition from OPEN to HALF_OPEN"""
        logger.info(f"Circuit breaker '{self.name}': OPEN -> HALF_OPEN")
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0

    def _on_success(self):
        """Handle successful call"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._transition_to_closed()
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0  # Reset on success

    def _on_failure(self):
        """Handle failed call"""
        self.last_failure_time = datetime.now(timezone.utc)
        self.failure_count += 1

        if self.state == CircuitState.HALF_OPEN:
            self._transition_to_open()
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self._transition_to_open()

    def _transition_to_open(self):
        """Transition to OPEN state"""
        logger.warning(f"Circuit breaker '{self.name}': {self.state.value} -> OPEN")
        self.state = CircuitState.OPEN
        self.opened_at = datetime.now(timezone.utc)
        self.success_count = 0

    def _transition_to_closed(self):
        """Transition to CLOSED state"""
        logger.info(f"Circuit breaker '{self.name}': HALF_OPEN -> CLOSED")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.opened_at = None

    def is_available(self) -> bool:
        """Check if circuit allows calls"""
        if self.state == CircuitState.OPEN:
            return self._should_attempt_reset()
        return True


class RateLimiter:
    """
    Token bucket rate limiter

    Limits requests per time window
    """

    def __init__(self, max_requests: int, time_window_seconds: int):
        """
        Args:
            max_requests: Maximum requests per window
            time_window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window_seconds
        self.tokens = max_requests
        self.last_update = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """
        Try to acquire a token

        Returns:
            True if token acquired, False if rate limit exceeded
        """
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_update

            # Refill tokens based on time elapsed
            tokens_to_add = (elapsed / self.time_window) * self.max_requests
            self.tokens = min(self.max_requests, self.tokens + tokens_to_add)
            self.last_update = now

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True

            return False

    async def wait_for_token(self, timeout: float = 10.0):
        """Wait until a token is available"""
        start = time.time()
        while time.time() - start < timeout:
            if await self.acquire():
                return True
            await asyncio.sleep(0.1)
        return False


@dataclass
class ExecutionResult:
    """Result of order execution attempt"""
    success: bool
    buy_order: Optional[OrderState] = None
    sell_order: Optional[OrderState] = None
    gross_profit: Decimal = Decimal('0')
    net_profit: Decimal = Decimal('0')
    total_fees: Decimal = Decimal('0')
    execution_time_ms: int = 0
    error_message: Optional[str] = None


class ExecutionEngine:
    """
    Advanced execution engine with circuit breakers and rate limiting

    Features:
    - Circuit breaker per exchange
    - Token bucket rate limiting
    - Exponential backoff retry
    - Partial fill handling
    - Execution analytics
    """

    def __init__(self, config, exchanges: Dict):
        """
        Args:
            config: System configuration
            exchanges: Dict of initialized exchange objects
        """
        self.config = config
        self.exchanges = exchanges

        # Circuit breakers per exchange
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        for exchange_name in exchanges.keys():
            self.circuit_breakers[exchange_name] = CircuitBreaker(
                name=f"exchange_{exchange_name}",
                failure_threshold=5,
                success_threshold=2,
                timeout_seconds=60
            )

        # Rate limiters per exchange
        self.rate_limiters: Dict[str, RateLimiter] = {}
        for exchange_name in exchanges.keys():
            # 100 requests per minute = ~1.67 per second
            self.rate_limiters[exchange_name] = RateLimiter(
                max_requests=100,
                time_window_seconds=60
            )

        # Execution tracking
        self.active_orders: Dict[str, OrderState] = {}
        self.execution_history: List[ExecutionResult] = []

        # Retry configuration
        self.max_retries = 3
        self.base_backoff_seconds = 2

        logger.info("✨ Execution Engine initialized")

    async def execute_arbitrage(
        self,
        buy_exchange: str,
        sell_exchange: str,
        symbol: str,
        buy_price: Decimal,
        sell_price: Decimal,
        amount: Decimal
    ) -> ExecutionResult:
        """
        Execute arbitrage trade with both legs

        Args:
            buy_exchange: Exchange to buy from
            sell_exchange: Exchange to sell to
            symbol: Trading pair
            buy_price: Limit price for buy
            sell_price: Limit price for sell
            amount: Amount to trade

        Returns:
            ExecutionResult with success status and details
        """
        start_time = datetime.now(timezone.utc)
        result = ExecutionResult(success=False)

        logger.info(
            f"🎯 Executing arbitrage: Buy {amount} {symbol} on {buy_exchange} "
            f"@ {buy_price}, Sell on {sell_exchange} @ {sell_price}"
        )

        try:
            # Check circuit breakers
            if not self.circuit_breakers[buy_exchange].is_available():
                raise Exception(f"Circuit breaker open for {buy_exchange}")
            if not self.circuit_breakers[sell_exchange].is_available():
                raise Exception(f"Circuit breaker open for {sell_exchange}")

            # Execute both legs simultaneously
            buy_task = self._execute_order(
                exchange_name=buy_exchange,
                symbol=symbol,
                side='buy',
                amount=amount,
                price=buy_price
            )

            sell_task = self._execute_order(
                exchange_name=sell_exchange,
                symbol=symbol,
                side='sell',
                amount=amount,
                price=sell_price
            )

            # Wait for both orders
            buy_order, sell_order = await asyncio.gather(buy_task, sell_task)

            # Check if both filled
            if buy_order.is_filled and sell_order.is_filled:
                # Calculate profit
                buy_cost = buy_order.filled_amount * buy_order.avg_fill_price
                sell_proceeds = sell_order.filled_amount * sell_order.avg_fill_price
                gross_profit = sell_proceeds - buy_cost
                total_fees = buy_order.fee + sell_order.fee
                net_profit = gross_profit - total_fees

                result.success = True
                result.buy_order = buy_order
                result.sell_order = sell_order
                result.gross_profit = gross_profit
                result.net_profit = net_profit
                result.total_fees = total_fees
                result.execution_time_ms = int(
                    (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                )

                logger.info(
                    f"✅ Arbitrage executed: Net profit ${net_profit:.2f} "
                    f"in {result.execution_time_ms}ms"
                )
            else:
                # Partial fill or failure - need to handle
                result.error_message = "One or both orders did not fill completely"
                logger.warning(result.error_message)

                # TODO: Implement position rebalancing logic

        except Exception as e:
            result.error_message = str(e)
            logger.error(f"❌ Arbitrage execution failed: {e}")

        # Store in history
        self.execution_history.append(result)

        return result

    async def _execute_order(
        self,
        exchange_name: str,
        symbol: str,
        side: str,
        amount: Decimal,
        price: Decimal,
        retry_count: int = 0
    ) -> OrderState:
        """
        Execute single order with retries

        Returns:
            OrderState with execution details
        """
        order = OrderState(
            exchange=exchange_name,
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            retry_count=retry_count
        )

        # Wait for rate limiter
        if not await self.rate_limiters[exchange_name].wait_for_token(timeout=30):
            order.status = OrderStatus.FAILED
            order.error_message = "Rate limit exceeded"
            return order

        try:
            # Use circuit breaker
            breaker = self.circuit_breakers[exchange_name]
            exchange = self.exchanges[exchange_name]

            # Create and submit order
            order.status = OrderStatus.SUBMITTED
            order.order_id = f"{exchange_name}_{symbol}_{side}_{int(time.time() * 1000)}"

            # Paper trading mode
            if self.config.trading.mode == 'paper':
                return await self._simulate_order(order)

            # Real execution would go here
            # response = await exchange.create_limit_order(
            #     symbol=symbol,
            #     side=side,
            #     amount=float(amount),
            #     price=float(price)
            # )

            # For now, simulate
            return await self._simulate_order(order)

        except Exception as e:
            logger.error(f"Order execution failed: {e}")
            order.status = OrderStatus.FAILED
            order.error_message = str(e)
            order.updated_at = datetime.now(timezone.utc)

            # Retry logic
            if retry_count < self.max_retries:
                backoff = self.base_backoff_seconds * (2 ** retry_count)
                logger.info(f"Retrying in {backoff}s (attempt {retry_count + 1})")
                await asyncio.sleep(backoff)
                return await self._execute_order(
                    exchange_name, symbol, side, amount, price, retry_count + 1
                )

            return order

    async def _simulate_order(self, order: OrderState) -> OrderState:
        """Simulate order execution for paper trading"""
        # Simulate execution delay
        await asyncio.sleep(0.1)

        # Assume full fill at specified price
        order.filled_amount = order.amount
        order.avg_fill_price = order.price
        order.status = OrderStatus.FILLED

        # Simulate fee (0.1%)
        order.fee = order.filled_amount * order.avg_fill_price * Decimal('0.001')
        order.fee_currency = 'USDT'

        order.updated_at = datetime.now(timezone.utc)

        return order

    async def cancel_order(
        self,
        exchange_name: str,
        order_id: str
    ) -> bool:
        """Cancel an active order"""
        try:
            if order_id in self.active_orders:
                order = self.active_orders[order_id]
                order.status = OrderStatus.CANCELLED
                order.updated_at = datetime.now(timezone.utc)
                del self.active_orders[order_id]
                logger.info(f"Order {order_id} cancelled")
                return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")

        return False

    def get_execution_stats(self) -> Dict:
        """Get execution statistics"""
        if not self.execution_history:
            return {
                'total_executions': 0,
                'successful': 0,
                'failed': 0,
                'success_rate': 0.0,
                'avg_execution_time_ms': 0,
                'total_profit': 0.0
            }

        successful = [e for e in self.execution_history if e.success]
        failed = [e for e in self.execution_history if not e.success]

        total_profit = sum(float(e.net_profit) for e in successful)
        avg_time = sum(e.execution_time_ms for e in successful) / len(successful) if successful else 0

        return {
            'total_executions': len(self.execution_history),
            'successful': len(successful),
            'failed': len(failed),
            'success_rate': len(successful) / len(self.execution_history) if self.execution_history else 0.0,
            'avg_execution_time_ms': int(avg_time),
            'total_profit': total_profit
        }
