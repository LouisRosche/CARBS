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
import random
import re
import uuid
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import logging
import time

logger = logging.getLogger(__name__)

# Import centralized defaults
from ..config.defaults import TRADING, CIRCUIT_BREAKER, RETRY

# Import exchange types for real execution
from ..exchanges import OrderSide, OrderType, OrderStatus as ExchangeOrderStatus

# Import balance manager for validation
from .balance_manager import BalanceManager, parse_symbol, InsufficientBalanceError

# Validation constants (using centralized defaults)
SYMBOL_PATTERN = re.compile(r'^[A-Z0-9]{2,10}/[A-Z0-9]{2,10}$')
MIN_TRADE_AMOUNT = TRADING.MIN_TRADE_AMOUNT
MAX_TRADE_AMOUNT = TRADING.MAX_TRADE_AMOUNT
MIN_PRICE = TRADING.MIN_PRICE
MAX_PRICE = TRADING.MAX_PRICE


class ValidationError(Exception):
    """Raised when input validation fails"""
    pass


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class OrderStatus(Enum):
    """Order execution status"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"  # Fixed: was PARTIAL
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
        return self.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]

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
        failure_threshold: int = None,
        success_threshold: int = None,
        timeout_seconds: int = None
    ):
        """
        Args:
            name: Circuit breaker identifier
            failure_threshold: Failures before opening circuit (default from config)
            success_threshold: Successes in half-open before closing (default from config)
            timeout_seconds: Time to wait before trying half-open (default from config)
        """
        self.name = name
        self.failure_threshold = failure_threshold or CIRCUIT_BREAKER.FAILURE_THRESHOLD
        self.success_threshold = success_threshold or CIRCUIT_BREAKER.SUCCESS_THRESHOLD
        self.timeout_seconds = timeout_seconds or CIRCUIT_BREAKER.TIMEOUT_SECONDS

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

    def __init__(
        self,
        config,
        exchanges: Dict,
        balance_manager: Optional[BalanceManager] = None
    ):
        """
        Args:
            config: System configuration
            exchanges: Dict of initialized exchange objects
            balance_manager: Optional BalanceManager for balance validation
        """
        self.config = config
        self.exchanges = exchanges
        self.balance_manager = balance_manager

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

        # Execution tracking with thread-safe access
        self.active_orders: Dict[str, OrderState] = {}
        self.execution_history: List[ExecutionResult] = []
        self._orders_lock = asyncio.Lock()  # Protects active_orders and execution_history

        # Retry configuration (from centralized defaults)
        self.max_retries = RETRY.MAX_RETRIES
        self.base_backoff_seconds = RETRY.BASE_BACKOFF_SECONDS

        logger.info("✨ Execution Engine initialized")

    def _validate_exchange(self, exchange_name: str) -> None:
        """Validate that an exchange exists and is configured"""
        if not exchange_name:
            raise ValidationError("Exchange name cannot be empty")
        if not isinstance(exchange_name, str):
            raise ValidationError(f"Exchange name must be a string, got {type(exchange_name)}")
        if exchange_name not in self.exchanges:
            available = list(self.exchanges.keys())
            raise ValidationError(
                f"Exchange '{exchange_name}' not configured. Available: {available}"
            )

    def _validate_symbol(self, symbol: str) -> None:
        """Validate trading pair symbol format"""
        if not symbol:
            raise ValidationError("Symbol cannot be empty")
        if not isinstance(symbol, str):
            raise ValidationError(f"Symbol must be a string, got {type(symbol)}")
        # Normalize and validate format (e.g., BTC/USDT)
        symbol_upper = symbol.upper()
        if not SYMBOL_PATTERN.match(symbol_upper):
            raise ValidationError(
                f"Invalid symbol format: '{symbol}'. Expected format: BASE/QUOTE (e.g., BTC/USDT)"
            )

    def _validate_amount(self, amount: Decimal, context: str = "Amount") -> None:
        """Validate trade amount"""
        if amount is None:
            raise ValidationError(f"{context} cannot be None")

        # Convert to Decimal if needed
        if not isinstance(amount, Decimal):
            try:
                amount = Decimal(str(amount))
            except (InvalidOperation, ValueError, TypeError) as e:
                raise ValidationError(f"{context} must be a valid number: {e}")

        if amount <= 0:
            raise ValidationError(f"{context} must be positive, got {amount}")
        if amount < MIN_TRADE_AMOUNT:
            raise ValidationError(
                f"{context} {amount} below minimum {MIN_TRADE_AMOUNT}"
            )
        if amount > MAX_TRADE_AMOUNT:
            raise ValidationError(
                f"{context} {amount} exceeds maximum {MAX_TRADE_AMOUNT}"
            )

    def _validate_price(self, price: Decimal, context: str = "Price") -> None:
        """Validate price value"""
        if price is None:
            raise ValidationError(f"{context} cannot be None")

        # Convert to Decimal if needed
        if not isinstance(price, Decimal):
            try:
                price = Decimal(str(price))
            except (InvalidOperation, ValueError, TypeError) as e:
                raise ValidationError(f"{context} must be a valid number: {e}")

        if price <= 0:
            raise ValidationError(f"{context} must be positive, got {price}")
        if price < MIN_PRICE:
            raise ValidationError(
                f"{context} {price} below minimum {MIN_PRICE}"
            )
        if price > MAX_PRICE:
            raise ValidationError(
                f"{context} {price} exceeds maximum {MAX_PRICE}"
            )

    def _validate_side(self, side: str) -> None:
        """Validate order side"""
        if not side:
            raise ValidationError("Order side cannot be empty")
        if side.lower() not in ('buy', 'sell'):
            raise ValidationError(
                f"Invalid order side: '{side}'. Must be 'buy' or 'sell'"
            )

    def _validate_arbitrage_inputs(
        self,
        buy_exchange: str,
        sell_exchange: str,
        symbol: str,
        buy_price: Decimal,
        sell_price: Decimal,
        amount: Decimal
    ) -> None:
        """
        Comprehensive validation for arbitrage execution inputs.

        Raises:
            ValidationError: If any input is invalid
        """
        # Validate exchanges
        self._validate_exchange(buy_exchange)
        self._validate_exchange(sell_exchange)

        if buy_exchange == sell_exchange:
            raise ValidationError(
                f"Buy and sell exchange cannot be the same: '{buy_exchange}'"
            )

        # Validate symbol
        self._validate_symbol(symbol)

        # Validate prices
        self._validate_price(buy_price, "Buy price")
        self._validate_price(sell_price, "Sell price")

        # Validate arbitrage makes sense (sell > buy for profit)
        if sell_price <= buy_price:
            raise ValidationError(
                f"Unprofitable arbitrage: sell price ({sell_price}) must exceed "
                f"buy price ({buy_price})"
            )

        # Validate amount
        self._validate_amount(amount)

        logger.debug(
            f"Validation passed for arbitrage: {buy_exchange}->{sell_exchange} "
            f"{symbol} amount={amount} buy@{buy_price} sell@{sell_price}"
        )

    def validate_order_book_depth(
        self,
        orderbook: 'EnhancedOrderBook',
        side: str,
        amount: Decimal,
        limit_price: Decimal,
        max_slippage_percent: Decimal = Decimal('0.5')
    ) -> tuple[bool, str, Decimal]:
        """
        Validate that order can be filled within acceptable slippage from order book depth.

        Args:
            orderbook: Order book with bids/asks
            side: 'buy' or 'sell'
            amount: Amount to trade
            limit_price: Expected execution price
            max_slippage_percent: Maximum acceptable slippage (default 0.5%)

        Returns:
            Tuple of (is_valid, reason, estimated_avg_price)
        """
        if not orderbook:
            return False, "Order book not available", Decimal('0')

        # Get relevant side of the book
        if side.lower() == 'buy':
            # Buying: look at asks (we take liquidity from asks)
            levels = orderbook.asks if hasattr(orderbook, 'asks') else []
        else:
            # Selling: look at bids (we take liquidity from bids)
            levels = orderbook.bids if hasattr(orderbook, 'bids') else []

        if not levels:
            return False, f"No {side} liquidity in order book", Decimal('0')

        # Calculate how much of order can be filled and at what average price
        remaining = amount
        total_cost = Decimal('0')
        total_filled = Decimal('0')

        for price, qty in levels:
            if remaining <= 0:
                break

            # Convert to Decimal if needed
            price = Decimal(str(price)) if not isinstance(price, Decimal) else price
            qty = Decimal(str(qty)) if not isinstance(qty, Decimal) else qty

            # For buy orders, only consider asks at or below our limit
            # For sell orders, only consider bids at or above our limit
            if side.lower() == 'buy' and price > limit_price * (1 + max_slippage_percent / 100):
                break
            if side.lower() == 'sell' and price < limit_price * (1 - max_slippage_percent / 100):
                break

            fill_qty = min(remaining, qty)
            total_cost += fill_qty * price
            total_filled += fill_qty
            remaining -= fill_qty

        # Check if we can fill the full order
        if total_filled < amount:
            fill_percent = (total_filled / amount * 100) if amount > 0 else Decimal('0')
            return False, (
                f"Insufficient liquidity: can only fill {total_filled:.4f} of {amount:.4f} "
                f"({fill_percent:.1f}%) within {max_slippage_percent}% slippage"
            ), Decimal('0')

        # Calculate average fill price
        avg_price = total_cost / total_filled if total_filled > 0 else limit_price

        # Calculate actual slippage
        if side.lower() == 'buy':
            slippage = ((avg_price - limit_price) / limit_price) * 100
        else:
            slippage = ((limit_price - avg_price) / limit_price) * 100

        if slippage > max_slippage_percent:
            return False, (
                f"Slippage too high: {slippage:.2f}% exceeds max {max_slippage_percent}%"
            ), avg_price

        logger.debug(
            f"Order book validation passed: {side} {amount} @ {limit_price}, "
            f"estimated avg price: {avg_price:.4f}, slippage: {slippage:.3f}%"
        )

        return True, "OK", avg_price

    async def execute_arbitrage(
        self,
        buy_exchange: str,
        sell_exchange: str,
        symbol: str,
        buy_price: Decimal,
        sell_price: Decimal,
        amount: Decimal,
        buy_orderbook: 'EnhancedOrderBook' = None,
        sell_orderbook: 'EnhancedOrderBook' = None,
        max_slippage_percent: Decimal = Decimal('0.5')
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
            buy_orderbook: Order book for buy exchange (for depth validation)
            sell_orderbook: Order book for sell exchange (for depth validation)
            max_slippage_percent: Maximum acceptable slippage per leg

        Returns:
            ExecutionResult with success status and details
        """
        start_time = datetime.now(timezone.utc)
        result = ExecutionResult(success=False)

        # Validate all inputs before proceeding
        try:
            self._validate_arbitrage_inputs(
                buy_exchange=buy_exchange,
                sell_exchange=sell_exchange,
                symbol=symbol,
                buy_price=buy_price,
                sell_price=sell_price,
                amount=amount
            )
        except ValidationError as e:
            result.error_message = f"Validation failed: {e}"
            logger.error(f"❌ Arbitrage validation failed: {e}")
            return result

        # Validate order book depth if order books provided
        if buy_orderbook:
            valid, reason, _ = self.validate_order_book_depth(
                orderbook=buy_orderbook,
                side='buy',
                amount=amount,
                limit_price=buy_price,
                max_slippage_percent=max_slippage_percent
            )
            if not valid:
                result.error_message = f"Buy order book validation failed: {reason}"
                logger.warning(f"⚠️ {result.error_message}")
                return result

        if sell_orderbook:
            valid, reason, _ = self.validate_order_book_depth(
                orderbook=sell_orderbook,
                side='sell',
                amount=amount,
                limit_price=sell_price,
                max_slippage_percent=max_slippage_percent
            )
            if not valid:
                result.error_message = f"Sell order book validation failed: {reason}"
                logger.warning(f"⚠️ {result.error_message}")
                return result

        # Parse symbol to get base and quote assets
        base_asset, quote_asset = parse_symbol(symbol)

        # Validate balances if balance manager is available
        if self.balance_manager:
            valid, reason = await self.balance_manager.validate_arbitrage(
                buy_exchange=buy_exchange,
                sell_exchange=sell_exchange,
                base_asset=base_asset,
                quote_asset=quote_asset,
                amount=amount,
                buy_price=buy_price,
                sell_price=sell_price
            )
            if not valid:
                result.error_message = f"Balance validation failed: {reason}"
                logger.error(f"❌ {result.error_message}")
                return result

            # Lock balances to prevent double-spending
            trade_id = f"arb_{uuid.uuid4().hex[:16]}"
            quote_lock = await self.balance_manager.lock_balance(
                exchange=buy_exchange,
                asset=quote_asset,
                amount=amount * buy_price,
                trade_id=trade_id
            )
            base_lock = await self.balance_manager.lock_balance(
                exchange=sell_exchange,
                asset=base_asset,
                amount=amount,
                trade_id=trade_id
            )
        else:
            quote_lock = None
            base_lock = None
            # CRITICAL: Refuse to execute live trades without balance validation
            if self.config.trading.mode != 'paper':
                result.error_message = "Balance manager required for live trading"
                logger.error("❌ Cannot execute live trades without balance manager!")
                return result
            logger.warning("No balance manager - paper trading without balance validation")

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

            # Wait for both orders - use return_exceptions to avoid orphaned positions
            results = await asyncio.gather(buy_task, sell_task, return_exceptions=True)

            # Check for exceptions
            buy_order = results[0]
            sell_order = results[1]

            # Handle exceptions from either leg
            if isinstance(buy_order, Exception):
                result.error_message = f"Buy order failed: {buy_order}"
                logger.error(result.error_message)
                # If sell succeeded, need to unwind
                if not isinstance(sell_order, Exception) and sell_order.is_filled:
                    logger.warning("Unwinding sell position due to failed buy")
                    try:
                        unwind = await self._execute_order(
                            sell_exchange, symbol, 'buy',
                            sell_order.filled_amount, sell_order.avg_fill_price
                        )
                        if not unwind.is_filled:
                            logger.critical(
                                f"🚨 UNWIND FAILED: Could not buy back {sell_order.filled_amount} "
                                f"{symbol} on {sell_exchange}. ORPHANED POSITION — manual intervention required!"
                            )
                            result.error_message += f"; UNWIND FAILED: {unwind.error_message}"
                    except Exception as unwind_err:
                        logger.critical(
                            f"🚨 UNWIND EXCEPTION: {unwind_err}. "
                            f"Orphaned sell of {sell_order.filled_amount} {symbol} on {sell_exchange}!"
                        )
                        result.error_message += f"; UNWIND EXCEPTION: {unwind_err}"
                return result

            if isinstance(sell_order, Exception):
                result.error_message = f"Sell order failed: {sell_order}"
                logger.error(result.error_message)
                # If buy succeeded, need to unwind
                if buy_order.is_filled:
                    logger.warning("Unwinding buy position due to failed sell")
                    try:
                        unwind = await self._execute_order(
                            buy_exchange, symbol, 'sell',
                            buy_order.filled_amount, buy_order.avg_fill_price
                        )
                        if not unwind.is_filled:
                            logger.critical(
                                f"🚨 UNWIND FAILED: Could not sell back {buy_order.filled_amount} "
                                f"{symbol} on {buy_exchange}. ORPHANED POSITION — manual intervention required!"
                            )
                            result.error_message += f"; UNWIND FAILED: {unwind.error_message}"
                    except Exception as unwind_err:
                        logger.critical(
                            f"🚨 UNWIND EXCEPTION: {unwind_err}. "
                            f"Orphaned buy of {buy_order.filled_amount} {symbol} on {buy_exchange}!"
                        )
                        result.error_message += f"; UNWIND EXCEPTION: {unwind_err}"
                return result

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
                # Partial fill or failure - need to handle position rebalancing
                result.error_message = "One or both orders did not fill completely"
                logger.warning(result.error_message)

                # Implement position rebalancing logic
                await self._rebalance_partial_fills(
                    buy_order=buy_order,
                    sell_order=sell_order,
                    symbol=symbol,
                    result=result
                )

        except Exception as e:
            result.error_message = str(e)
            logger.error(f"❌ Arbitrage execution failed: {e}")

        finally:
            # Release balance locks
            if self.balance_manager:
                if quote_lock:
                    await self.balance_manager.release_lock(quote_lock)
                if base_lock:
                    await self.balance_manager.release_lock(base_lock)

        # Store in history (thread-safe)
        async with self._orders_lock:
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
        # Create initial order state
        order = OrderState(
            exchange=exchange_name,
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            retry_count=retry_count
        )

        # Validate inputs (defensive - should already be validated by caller)
        try:
            self._validate_exchange(exchange_name)
            self._validate_symbol(symbol)
            self._validate_side(side)
            self._validate_amount(amount)
            self._validate_price(price)
        except ValidationError as e:
            order.status = OrderStatus.FAILED
            order.error_message = f"Validation failed: {e}"
            logger.error(f"Order validation failed: {e}")
            return order

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

            # Paper trading mode - use simulation
            if self.config.trading.mode == 'paper':
                order.order_id = f"{exchange_name}_{symbol}_{side}_{int(time.time() * 1000)}"
                return await self._simulate_order(order)

            # LIVE TRADING MODE - Real exchange execution
            logger.info(f"🔴 LIVE ORDER: {side.upper()} {amount} {symbol} @ {price} on {exchange_name}")

            # Convert symbol format for exchange (exchange-specific formatting)
            exchange_symbol = self._format_symbol_for_exchange(exchange_name, symbol)

            # Determine order side
            order_side = OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL

            try:
                # Submit order to exchange — wrapped with circuit breaker
                protected_create = breaker.call(exchange.create_order)
                exchange_order = await protected_create(
                    symbol=exchange_symbol,
                    side=order_side,
                    order_type=OrderType.LIMIT,
                    quantity=amount,
                    price=price
                )

                # Validate order_id before proceeding — an untracked order is dangerous
                if not exchange_order.order_id:
                    order.status = OrderStatus.FAILED
                    order.error_message = "Exchange returned empty order_id — order may be orphaned"
                    logger.critical(
                        f"🚨 CRITICAL: Exchange {exchange_name} returned empty order_id for "
                        f"{side} {amount} {symbol}. Manual reconciliation may be required."
                    )
                    return order

                # Map exchange order to our order state
                order.order_id = exchange_order.order_id
                order.status = self._map_exchange_status(exchange_order.status)
                order.filled_amount = exchange_order.filled_quantity
                order.avg_fill_price = exchange_order.avg_fill_price or price
                order.fee = exchange_order.fee
                order.fee_currency = exchange_order.fee_asset
                order.updated_at = datetime.now(timezone.utc)

                logger.info(
                    f"✅ Order submitted: {order.order_id} status={order.status.value}"
                )

                # Wait for fill (with timeout)
                if order.status not in [OrderStatus.FILLED, OrderStatus.FAILED, OrderStatus.CANCELLED]:
                    order = await self._wait_for_fill(exchange, exchange_symbol, order, exchange_name=exchange_name)

                return order

            except Exception as e:
                logger.error(f"Exchange API error: {e}")
                raise

        except Exception as e:
            logger.error(f"Order execution failed: {e}")
            order.status = OrderStatus.FAILED
            order.error_message = str(e)
            order.updated_at = datetime.now(timezone.utc)

            # Retry logic with jitter to prevent thundering herd
            if retry_count < self.max_retries:
                base_backoff = self.base_backoff_seconds * (2 ** retry_count)
                # Add jitter: 50-150% of base backoff
                jitter = base_backoff * (0.5 + random.random())
                backoff = base_backoff * 0.5 + jitter
                logger.info(f"Retrying in {backoff:.2f}s (attempt {retry_count + 1})")
                await asyncio.sleep(backoff)
                return await self._execute_order(
                    exchange_name, symbol, side, amount, price, retry_count + 1
                )

            return order

    def _map_exchange_status(self, exchange_status: ExchangeOrderStatus) -> OrderStatus:
        """Map exchange order status to our internal status"""
        status_map = {
            ExchangeOrderStatus.PENDING: OrderStatus.PENDING,
            ExchangeOrderStatus.OPEN: OrderStatus.SUBMITTED,
            ExchangeOrderStatus.PARTIALLY_FILLED: OrderStatus.PARTIALLY_FILLED,
            ExchangeOrderStatus.FILLED: OrderStatus.FILLED,
            ExchangeOrderStatus.CANCELLED: OrderStatus.CANCELLED,
            ExchangeOrderStatus.REJECTED: OrderStatus.FAILED,
            ExchangeOrderStatus.EXPIRED: OrderStatus.TIMEOUT,
        }
        return status_map.get(exchange_status, OrderStatus.PENDING)

    @staticmethod
    def _format_symbol_for_exchange(exchange_name: str, symbol: str) -> str:
        """
        Format trading symbol for the specific exchange's API.

        Different exchanges expect different symbol formats:
        - Binance, MEXC: BTCUSDT (no separator)
        - KuCoin: BTC-USDT (dash separator)
        - Others: fall back to the canonical BTC/USDT (slash)
        """
        # Exchanges that use no separator
        no_separator = {"binance", "mexc", "gate", "bybit"}
        # Exchanges that use dash separator
        dash_separator = {"kucoin", "okx"}

        name_lower = exchange_name.lower()
        if name_lower in no_separator:
            return symbol.replace("/", "")
        elif name_lower in dash_separator:
            return symbol.replace("/", "-")
        else:
            # Default: pass through the canonical format (BTC/USDT)
            # Most ccxt exchanges accept this
            return symbol

    async def _wait_for_fill(
        self,
        exchange,
        symbol: str,
        order: OrderState,
        timeout_seconds: int = None,
        exchange_name: str = ""
    ) -> OrderState:
        """
        Wait for order to fill with polling.

        Args:
            exchange: Exchange instance
            symbol: Trading symbol
            order: Order to wait for
            timeout_seconds: Max time to wait (default from config)

        Returns:
            Updated order state
        """
        timeout = timeout_seconds or self.config.trading.order_timeout_seconds
        start = time.time()
        poll_interval = 0.5  # Start with 500ms

        logger.debug(f"Waiting for order {order.order_id} to fill (timeout={timeout}s)")

        # Get circuit breaker for this exchange (if available)
        breaker = self.circuit_breakers.get(exchange_name) if exchange_name else None

        while time.time() - start < timeout:
            try:
                # Query order status from exchange — with circuit breaker if available
                if breaker:
                    protected_get = breaker.call(exchange.get_order)
                    exchange_order = await protected_get(symbol, order.order_id)
                else:
                    exchange_order = await exchange.get_order(symbol, order.order_id)

                order.status = self._map_exchange_status(exchange_order.status)
                order.filled_amount = exchange_order.filled_quantity
                order.avg_fill_price = exchange_order.avg_fill_price or order.price
                order.fee = exchange_order.fee
                order.updated_at = datetime.now(timezone.utc)

                # Check if terminal state
                if order.status in [OrderStatus.FILLED, OrderStatus.FAILED, OrderStatus.CANCELLED]:
                    logger.info(
                        f"Order {order.order_id} reached terminal state: {order.status.value} "
                        f"(filled={order.filled_amount})"
                    )
                    return order

                # Partial fill progress
                if order.filled_amount > 0:
                    logger.debug(
                        f"Order {order.order_id} partial fill: {order.filled_amount}/{order.amount}"
                    )

            except Exception as e:
                logger.warning(f"Error polling order status: {e}")

            # Exponential backoff for polling (max 2 seconds)
            await asyncio.sleep(min(poll_interval, 2.0))
            poll_interval *= 1.5

        # Timeout - order didn't fill
        order.status = OrderStatus.TIMEOUT
        order.error_message = f"Order timeout after {timeout}s"
        logger.warning(f"Order {order.order_id} timed out after {timeout}s")

        # Try to cancel the unfilled order — with circuit breaker if available
        try:
            if breaker:
                protected_cancel = breaker.call(exchange.cancel_order)
                cancelled = await protected_cancel(symbol, order.order_id)
            else:
                cancelled = await exchange.cancel_order(symbol, order.order_id)
            if cancelled:
                order.status = OrderStatus.CANCELLED
                logger.info(f"Cancelled timed-out order {order.order_id}")
            else:
                # Cancel returned False — order may have filled while we tried to cancel
                logger.warning(
                    f"Cancel returned False for order {order.order_id} — "
                    f"order may have filled during cancellation. Verifying final state..."
                )
                try:
                    if breaker:
                        protected_get = breaker.call(exchange.get_order)
                        final_state = await protected_get(symbol, order.order_id)
                    else:
                        final_state = await exchange.get_order(symbol, order.order_id)
                    order.status = self._map_exchange_status(final_state.status)
                    order.filled_amount = final_state.filled_quantity
                    order.avg_fill_price = final_state.avg_fill_price or order.price
                    logger.info(
                        f"Final state for order {order.order_id}: "
                        f"status={order.status.value}, filled={order.filled_amount}"
                    )
                except Exception as verify_err:
                    logger.critical(
                        f"🚨 Cannot verify final state of order {order.order_id}: {verify_err}. "
                        f"Order may be live on exchange — manual check required!"
                    )
        except Exception as e:
            logger.critical(
                f"🚨 Failed to cancel timed-out order {order.order_id}: {e}. "
                f"Order may still be live on exchange — manual intervention required!"
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

    async def _rebalance_partial_fills(
        self,
        buy_order: 'OrderState',
        sell_order: 'OrderState',
        symbol: str,
        result: 'ArbitrageResult'
    ) -> None:
        """
        Handle position rebalancing when arbitrage orders partially fill

        Strategy:
        1. If buy filled more than sell: Sell excess on buy exchange
        2. If sell filled more than buy: Buy shortage on sell exchange
        3. Cancel any remaining unfilled portions

        This ensures we don't end up with unhedged positions.
        """
        buy_filled = buy_order.filled_amount or Decimal("0")
        sell_filled = sell_order.filled_amount or Decimal("0")

        logger.info(
            f"🔄 Rebalancing positions - Buy filled: {buy_filled}, Sell filled: {sell_filled}"
        )

        try:
            # Cancel any remaining open portions
            if buy_order.status == OrderStatus.PARTIALLY_FILLED and buy_order.order_id:
                await self.cancel_order(buy_order.exchange, buy_order.order_id)
                logger.info(f"Cancelled remaining buy order on {buy_order.exchange}")

            if sell_order.status == OrderStatus.PARTIALLY_FILLED and sell_order.order_id:
                await self.cancel_order(sell_order.exchange, sell_order.order_id)
                logger.info(f"Cancelled remaining sell order on {sell_order.exchange}")

            # Calculate imbalance
            imbalance = buy_filled - sell_filled

            if imbalance > Decimal("0.0001"):
                # We bought more than we sold - need to sell the excess
                logger.info(f"Selling excess {imbalance} {symbol} on {buy_order.exchange}")

                rebalance_order = await self._execute_order(
                    exchange_name=buy_order.exchange,
                    symbol=symbol,
                    side='sell',
                    amount=imbalance,
                    price=buy_order.avg_fill_price * Decimal("0.999")  # Slightly below to ensure fill
                )

                if rebalance_order.status == OrderStatus.FILLED:
                    # Adjust result for rebalancing trade
                    rebalance_value = rebalance_order.filled_amount * rebalance_order.avg_fill_price
                    result.gross_profit = (result.gross_profit or Decimal("0")) - rebalance_order.fee
                    result.net_profit = (result.net_profit or Decimal("0")) - rebalance_order.fee
                    logger.info(f"✅ Rebalanced by selling {imbalance} {symbol}")
                else:
                    result.error_message = (result.error_message or "") + f"; Rebalance sell failed"
                    logger.error(f"Failed to rebalance sell: {rebalance_order.error_message}")

            elif imbalance < Decimal("-0.0001"):
                # We sold more than we bought - need to buy the shortage
                shortage = abs(imbalance)
                logger.info(f"Buying shortage {shortage} {symbol} on {sell_order.exchange}")

                rebalance_order = await self._execute_order(
                    exchange_name=sell_order.exchange,
                    symbol=symbol,
                    side='buy',
                    amount=shortage,
                    price=sell_order.avg_fill_price * Decimal("1.001")  # Slightly above to ensure fill
                )

                if rebalance_order.status == OrderStatus.FILLED:
                    # Adjust result for rebalancing trade
                    result.gross_profit = (result.gross_profit or Decimal("0")) - rebalance_order.fee
                    result.net_profit = (result.net_profit or Decimal("0")) - rebalance_order.fee
                    logger.info(f"✅ Rebalanced by buying {shortage} {symbol}")
                else:
                    result.error_message = (result.error_message or "") + f"; Rebalance buy failed"
                    logger.error(f"Failed to rebalance buy: {rebalance_order.error_message}")

            else:
                # Positions are balanced (within tolerance)
                logger.info("Positions balanced after partial fills")

            # Record the rebalancing attempt
            result.success = buy_filled > 0 and sell_filled > 0  # Partial success if both had some fill

        except Exception as e:
            logger.error(f"Error during position rebalancing: {e}")
            result.error_message = (result.error_message or "") + f"; Rebalance error: {e}"

    async def cancel_order(
        self,
        exchange_name: str,
        order_id: str
    ) -> bool:
        """Cancel an active order (thread-safe)"""
        try:
            async with self._orders_lock:
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
        """Get execution statistics (thread-safe snapshot)"""
        # Take a snapshot to avoid race conditions during iteration
        history_snapshot = list(self.execution_history)

        if not history_snapshot:
            return {
                'total_executions': 0,
                'successful': 0,
                'failed': 0,
                'success_rate': 0.0,
                'avg_execution_time_ms': 0,
                'total_profit': 0.0
            }

        successful = [e for e in history_snapshot if e.success]
        failed = [e for e in history_snapshot if not e.success]

        total_profit = sum(float(e.net_profit) for e in successful)
        avg_time = sum(e.execution_time_ms for e in successful) / len(successful) if successful else 0

        return {
            'total_executions': len(history_snapshot),
            'successful': len(successful),
            'failed': len(failed),
            'success_rate': len(successful) / len(history_snapshot) if history_snapshot else 0.0,
            'avg_execution_time_ms': int(avg_time),
            'total_profit': total_profit
        }
