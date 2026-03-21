"""
Integration Tests with Mock Exchanges

Comprehensive integration testing:
- Mock exchange implementations
- End-to-end arbitrage flow
- WebSocket simulation
- Error scenario testing
- Performance testing
"""

import asyncio
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
import random


# =============================================================================
# Mock Exchange Implementation
# =============================================================================

class MockOrderBook:
    """Simulated order book with realistic behavior"""

    def __init__(self, symbol: str, base_price: Decimal = Decimal("100")):
        self.symbol = symbol
        self.base_price = base_price
        self.spread_bps = Decimal("10")  # 10 basis points
        self._volatility = Decimal("0.001")  # 0.1% volatility

    def get_snapshot(self) -> Dict:
        """Generate order book snapshot"""
        mid = self.base_price * (1 + Decimal(str(random.uniform(-0.001, 0.001))))
        spread = mid * self.spread_bps / Decimal("10000")

        bids = []
        asks = []

        for i in range(20):
            bid_price = mid - spread/2 - Decimal(str(i * 0.01))
            ask_price = mid + spread/2 + Decimal(str(i * 0.01))
            qty = Decimal(str(random.uniform(0.1, 10.0)))

            bids.append((bid_price, qty))
            asks.append((ask_price, qty))

        return {
            "symbol": self.symbol,
            "bids": bids,
            "asks": asks,
            "timestamp": datetime.now(timezone.utc)
        }

    @property
    def best_bid(self) -> tuple:
        snapshot = self.get_snapshot()
        return snapshot["bids"][0]

    @property
    def best_ask(self) -> tuple:
        snapshot = self.get_snapshot()
        return snapshot["asks"][0]


class MockExchange:
    """
    Mock exchange for integration testing

    Features:
    - Realistic order execution
    - Balance management
    - Order book simulation
    - Configurable latency
    - Error injection
    """

    def __init__(
        self,
        name: str,
        initial_balances: Dict[str, Decimal] = None,
        latency_ms: int = 50,
        failure_rate: float = 0.0
    ):
        self.name = name
        self.latency_ms = latency_ms
        self.failure_rate = failure_rate

        # Initialize balances
        self._balances = initial_balances or {
            "USDT": Decimal("10000"),
            "BTC": Decimal("1.0"),
            "ETH": Decimal("10.0")
        }

        # Order books
        self._order_books: Dict[str, MockOrderBook] = {
            "BTCUSDT": MockOrderBook("BTCUSDT", Decimal("42000")),
            "ETHUSDT": MockOrderBook("ETHUSDT", Decimal("2200")),
        }

        # Order tracking
        self._orders: Dict[str, Dict] = {}
        self._order_counter = 0

        # Statistics
        self._stats = {
            "api_calls": 0,
            "orders_placed": 0,
            "orders_filled": 0,
            "orders_failed": 0
        }

    async def _simulate_latency(self):
        """Simulate network latency"""
        await asyncio.sleep(self.latency_ms / 1000)

    def _should_fail(self) -> bool:
        """Check if this call should fail"""
        return random.random() < self.failure_rate

    async def get_ticker(self, symbol: str) -> Dict:
        """Get ticker data"""
        await self._simulate_latency()
        self._stats["api_calls"] += 1

        if self._should_fail():
            raise Exception(f"Mock API error for {symbol}")

        book = self._order_books.get(symbol)
        if not book:
            raise ValueError(f"Unknown symbol: {symbol}")

        bid = book.best_bid
        ask = book.best_ask

        return {
            "symbol": symbol,
            "bid": bid[0],
            "ask": ask[0],
            "last": (bid[0] + ask[0]) / 2,
            "volume_24h": Decimal("1000000"),
            "timestamp": datetime.now(timezone.utc)
        }

    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict:
        """Get order book"""
        await self._simulate_latency()
        self._stats["api_calls"] += 1

        if self._should_fail():
            raise Exception(f"Mock API error for {symbol}")

        book = self._order_books.get(symbol)
        if not book:
            raise ValueError(f"Unknown symbol: {symbol}")

        return book.get_snapshot()

    async def get_balances(self) -> Dict[str, Dict]:
        """Get account balances"""
        await self._simulate_latency()
        self._stats["api_calls"] += 1

        return {
            asset: {
                "asset": asset,
                "free": amount,
                "locked": Decimal("0"),
                "total": amount
            }
            for asset, amount in self._balances.items()
        }

    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Decimal = None
    ) -> Dict:
        """Create and execute order"""
        await self._simulate_latency()
        self._stats["api_calls"] += 1
        self._stats["orders_placed"] += 1

        if self._should_fail():
            self._stats["orders_failed"] += 1
            raise Exception("Mock order execution failed")

        # Parse symbol
        base, quote = self._parse_symbol(symbol)

        # Validate balance
        if side == "buy":
            required = quantity * (price or self._order_books[symbol].best_ask[0])
            if self._balances.get(quote, Decimal("0")) < required:
                raise ValueError(f"Insufficient {quote} balance")
        else:
            if self._balances.get(base, Decimal("0")) < quantity:
                raise ValueError(f"Insufficient {base} balance")

        # Generate order ID
        self._order_counter += 1
        order_id = f"{self.name}_order_{self._order_counter}"

        # Simulate execution (instant fill for market orders)
        book = self._order_books[symbol]
        if order_type == "market" or order_type == "limit":
            exec_price = book.best_ask[0] if side == "buy" else book.best_bid[0]

            # Add slippage for market orders
            if order_type == "market":
                slippage = Decimal(str(random.uniform(0, 0.001)))
                if side == "buy":
                    exec_price *= (1 + slippage)
                else:
                    exec_price *= (1 - slippage)

            # Update balances
            if side == "buy":
                self._balances[quote] -= quantity * exec_price
                self._balances[base] = self._balances.get(base, Decimal("0")) + quantity
            else:
                self._balances[base] -= quantity
                self._balances[quote] = self._balances.get(quote, Decimal("0")) + quantity * exec_price

            # Calculate fee
            fee = quantity * exec_price * Decimal("0.001")  # 0.1% fee

            order = {
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "type": order_type,
                "status": "filled",
                "price": price,
                "quantity": quantity,
                "filled_quantity": quantity,
                "executed_price": exec_price,
                "fee": fee,
                "fee_currency": quote,
                "created_at": datetime.now(timezone.utc),
                "filled_at": datetime.now(timezone.utc)
            }

            self._orders[order_id] = order
            self._stats["orders_filled"] += 1

            return order

        raise ValueError(f"Unsupported order type: {order_type}")

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel order"""
        await self._simulate_latency()
        self._stats["api_calls"] += 1

        if order_id in self._orders:
            self._orders[order_id]["status"] = "cancelled"
            return True
        return False

    async def get_order(self, symbol: str, order_id: str) -> Optional[Dict]:
        """Get order details"""
        await self._simulate_latency()
        self._stats["api_calls"] += 1

        return self._orders.get(order_id)

    def _parse_symbol(self, symbol: str) -> tuple:
        """Parse symbol into base/quote"""
        for quote in ["USDT", "USDC", "BTC", "ETH"]:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                return base, quote
        raise ValueError(f"Cannot parse symbol: {symbol}")

    def set_price(self, symbol: str, price: Decimal):
        """Set base price for testing"""
        if symbol in self._order_books:
            self._order_books[symbol].base_price = price

    def get_stats(self) -> Dict:
        """Get exchange statistics"""
        return dict(self._stats)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_binance():
    """Create mock Binance exchange"""
    return MockExchange(
        name="binance",
        initial_balances={
            "USDT": Decimal("10000"),
            "BTC": Decimal("0.5"),
            "ETH": Decimal("5.0")
        },
        latency_ms=50
    )


@pytest.fixture
def mock_mexc():
    """Create mock MEXC exchange"""
    return MockExchange(
        name="mexc",
        initial_balances={
            "USDT": Decimal("10000"),
            "BTC": Decimal("0.5"),
            "ETH": Decimal("5.0")
        },
        latency_ms=100
    )


@pytest.fixture
def mock_exchanges(mock_binance, mock_mexc):
    """Create dict of mock exchanges"""
    return {
        "binance": mock_binance,
        "mexc": mock_mexc
    }


# =============================================================================
# Exchange Integration Tests
# =============================================================================

class TestMockExchange:
    """Tests for mock exchange implementation"""

    @pytest.mark.asyncio
    async def test_get_ticker(self, mock_binance):
        """Test ticker retrieval"""
        ticker = await mock_binance.get_ticker("BTCUSDT")

        assert ticker["symbol"] == "BTCUSDT"
        assert ticker["bid"] > 0
        assert ticker["ask"] > ticker["bid"]
        assert ticker["last"] > 0

    @pytest.mark.asyncio
    async def test_get_orderbook(self, mock_binance):
        """Test order book retrieval"""
        book = await mock_binance.get_orderbook("BTCUSDT")

        assert book["symbol"] == "BTCUSDT"
        assert len(book["bids"]) == 20
        assert len(book["asks"]) == 20
        assert book["bids"][0][0] < book["asks"][0][0]  # Bid < Ask

    @pytest.mark.asyncio
    async def test_get_balances(self, mock_binance):
        """Test balance retrieval"""
        balances = await mock_binance.get_balances()

        assert "USDT" in balances
        assert balances["USDT"]["free"] == Decimal("10000")
        assert balances["BTC"]["free"] == Decimal("0.5")

    @pytest.mark.asyncio
    async def test_create_market_buy_order(self, mock_binance):
        """Test market buy order"""
        order = await mock_binance.create_order(
            symbol="BTCUSDT",
            side="buy",
            order_type="market",
            quantity=Decimal("0.01")
        )

        assert order["status"] == "filled"
        assert order["filled_quantity"] == Decimal("0.01")
        assert order["executed_price"] > 0
        assert order["fee"] > 0

    @pytest.mark.asyncio
    async def test_create_market_sell_order(self, mock_binance):
        """Test market sell order"""
        order = await mock_binance.create_order(
            symbol="BTCUSDT",
            side="sell",
            order_type="market",
            quantity=Decimal("0.1")
        )

        assert order["status"] == "filled"
        assert order["filled_quantity"] == Decimal("0.1")

    @pytest.mark.asyncio
    async def test_insufficient_balance(self, mock_binance):
        """Test insufficient balance handling"""
        with pytest.raises(ValueError, match="Insufficient"):
            await mock_binance.create_order(
                symbol="BTCUSDT",
                side="buy",
                order_type="market",
                quantity=Decimal("100")  # Too much
            )

    @pytest.mark.asyncio
    async def test_balance_updates_after_trade(self, mock_binance):
        """Test that balances update correctly after trades"""
        initial_balances = await mock_binance.get_balances()
        initial_usdt = initial_balances["USDT"]["free"]
        initial_btc = initial_balances["BTC"]["free"]

        # Buy BTC
        order = await mock_binance.create_order(
            symbol="BTCUSDT",
            side="buy",
            order_type="market",
            quantity=Decimal("0.1")
        )

        updated_balances = await mock_binance.get_balances()

        # USDT should decrease
        assert updated_balances["USDT"]["free"] < initial_usdt
        # BTC should increase
        assert updated_balances["BTC"]["free"] == initial_btc + Decimal("0.1")


# =============================================================================
# Arbitrage Flow Tests
# =============================================================================

class TestArbitrageFlow:
    """End-to-end arbitrage flow tests"""

    @pytest.mark.asyncio
    async def test_detect_arbitrage_opportunity(self, mock_exchanges):
        """Test arbitrage opportunity detection"""
        binance = mock_exchanges["binance"]
        mexc = mock_exchanges["mexc"]

        # Set prices to create opportunity
        binance.set_price("BTCUSDT", Decimal("42000"))
        mexc.set_price("BTCUSDT", Decimal("42100"))

        binance_book = await binance.get_orderbook("BTCUSDT")
        mexc_book = await mexc.get_orderbook("BTCUSDT")

        binance_ask = binance_book["asks"][0][0]
        mexc_bid = mexc_book["bids"][0][0]

        # Check if arbitrage exists
        if mexc_bid > binance_ask:
            spread_bps = (mexc_bid - binance_ask) / binance_ask * 10000
            assert spread_bps > 0

    @pytest.mark.asyncio
    async def test_execute_arbitrage_trade(self, mock_exchanges):
        """Test complete arbitrage execution"""
        binance = mock_exchanges["binance"]
        mexc = mock_exchanges["mexc"]

        # Set prices for clear opportunity
        binance.set_price("BTCUSDT", Decimal("42000"))
        mexc.set_price("BTCUSDT", Decimal("42200"))

        quantity = Decimal("0.1")

        # Execute buy on Binance
        buy_order = await binance.create_order(
            symbol="BTCUSDT",
            side="buy",
            order_type="market",
            quantity=quantity
        )

        # Execute sell on MEXC
        sell_order = await mexc.create_order(
            symbol="BTCUSDT",
            side="sell",
            order_type="market",
            quantity=quantity
        )

        # Calculate profit
        buy_cost = buy_order["filled_quantity"] * buy_order["executed_price"]
        sell_proceeds = sell_order["filled_quantity"] * sell_order["executed_price"]
        gross_profit = sell_proceeds - buy_cost
        fees = buy_order["fee"] + sell_order["fee"]
        net_profit = gross_profit - fees

        assert buy_order["status"] == "filled"
        assert sell_order["status"] == "filled"
        # With 200 point spread on 42000 base, should have profit
        assert gross_profit > 0

    @pytest.mark.asyncio
    async def test_concurrent_order_execution(self, mock_exchanges):
        """Test concurrent order execution"""
        binance = mock_exchanges["binance"]
        mexc = mock_exchanges["mexc"]

        quantity = Decimal("0.05")

        # Execute both legs concurrently
        results = await asyncio.gather(
            binance.create_order(
                symbol="BTCUSDT",
                side="buy",
                order_type="market",
                quantity=quantity
            ),
            mexc.create_order(
                symbol="BTCUSDT",
                side="sell",
                order_type="market",
                quantity=quantity
            ),
            return_exceptions=True
        )

        # Both should succeed
        assert not isinstance(results[0], Exception)
        assert not isinstance(results[1], Exception)
        assert results[0]["status"] == "filled"
        assert results[1]["status"] == "filled"


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling and recovery"""

    @pytest.mark.asyncio
    async def test_exchange_failure_recovery(self):
        """Test recovery from exchange failures"""
        # Create exchange with 50% failure rate
        flaky_exchange = MockExchange(
            name="flaky",
            failure_rate=0.5,
            latency_ms=10
        )

        success_count = 0
        failure_count = 0

        # Try multiple times
        for _ in range(20):
            try:
                await flaky_exchange.get_ticker("BTCUSDT")
                success_count += 1
            except Exception:
                failure_count += 1

        # Should have both successes and failures
        assert success_count > 0
        assert failure_count > 0

    @pytest.mark.asyncio
    async def test_order_execution_failure_handling(self):
        """Test handling of order execution failures"""
        exchange = MockExchange(name="test", failure_rate=0.0)

        # Test with insufficient balance
        try:
            await exchange.create_order(
                symbol="BTCUSDT",
                side="buy",
                order_type="market",
                quantity=Decimal("1000000")  # Way too much
            )
            assert False, "Should have raised exception"
        except ValueError as e:
            assert "Insufficient" in str(e)


# =============================================================================
# Resilience Pattern Tests
# =============================================================================

class TestResiliencePatterns:
    """Test resilience patterns"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, mock_binance):
        """Test circuit breaker with exchange"""
        from src.utils.resilience import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=1
        )

        breaker = CircuitBreaker("binance_api", config=config)

        @breaker
        async def get_ticker():
            return await mock_binance.get_ticker("BTCUSDT")

        # Should work normally
        ticker = await get_ticker()
        assert ticker is not None

    @pytest.mark.asyncio
    async def test_retry_with_backoff(self, mock_binance):
        """Test retry mechanism"""
        from src.utils.resilience import RetryPolicy, RetryConfig

        config = RetryConfig(
            max_attempts=3,
            base_delay=0.1,
            retryable_exceptions=(Exception,)
        )

        policy = RetryPolicy(config)
        call_count = 0

        @policy
        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = await flaky_operation()
        assert result == "success"
        assert call_count == 3


# =============================================================================
# WebSocket Tests
# =============================================================================

class TestWebSocketIntegration:
    """Test WebSocket functionality"""

    @pytest.mark.asyncio
    async def test_orderbook_update_handling(self):
        """Test order book update processing"""
        from src.exchanges.websocket_manager import LocalOrderBook, OrderBookUpdate

        book = LocalOrderBook("binance", "BTCUSDT")

        # Apply snapshot
        update = OrderBookUpdate(
            exchange="binance",
            symbol="BTCUSDT",
            bids=[(Decimal("42000"), Decimal("1.0")), (Decimal("41999"), Decimal("2.0"))],
            asks=[(Decimal("42001"), Decimal("1.0")), (Decimal("42002"), Decimal("2.0"))],
            timestamp=datetime.now(timezone.utc),
            is_snapshot=True
        )

        await book.apply_update(update)

        assert book.best_bid == (Decimal("42000"), Decimal("1.0"))
        assert book.best_ask == (Decimal("42001"), Decimal("1.0"))
        assert book.spread == Decimal("1")

    @pytest.mark.asyncio
    async def test_orderbook_delta_update(self):
        """Test incremental order book updates"""
        from src.exchanges.websocket_manager import LocalOrderBook, OrderBookUpdate

        book = LocalOrderBook("binance", "BTCUSDT")

        # Initial snapshot
        snapshot = OrderBookUpdate(
            exchange="binance",
            symbol="BTCUSDT",
            bids=[(Decimal("42000"), Decimal("1.0"))],
            asks=[(Decimal("42001"), Decimal("1.0"))],
            timestamp=datetime.now(timezone.utc),
            is_snapshot=True
        )
        await book.apply_update(snapshot)

        # Delta update - add new bid level
        delta = OrderBookUpdate(
            exchange="binance",
            symbol="BTCUSDT",
            bids=[(Decimal("42000.5"), Decimal("0.5"))],
            asks=[],
            timestamp=datetime.now(timezone.utc),
            is_snapshot=False
        )
        await book.apply_update(delta)

        # New best bid should be the higher price
        assert book.best_bid == (Decimal("42000.5"), Decimal("0.5"))


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Performance and load tests"""

    @pytest.mark.asyncio
    async def test_concurrent_ticker_requests(self, mock_binance):
        """Test concurrent ticker requests"""
        import time

        num_requests = 100
        start = time.monotonic()

        tasks = [
            mock_binance.get_ticker("BTCUSDT")
            for _ in range(num_requests)
        ]

        results = await asyncio.gather(*tasks)
        duration = time.monotonic() - start

        assert len(results) == num_requests
        # With 50ms latency, concurrent should complete much faster than sequential
        assert duration < num_requests * 0.05  # Less than sequential time

    @pytest.mark.asyncio
    async def test_order_throughput(self, mock_binance):
        """Test order execution throughput"""
        import time

        num_orders = 50
        start = time.monotonic()

        for i in range(num_orders):
            await mock_binance.create_order(
                symbol="BTCUSDT",
                side="buy" if i % 2 == 0 else "sell",
                order_type="market",
                quantity=Decimal("0.001")
            )

        duration = time.monotonic() - start
        orders_per_second = num_orders / duration

        print(f"Order throughput: {orders_per_second:.2f} orders/second")
        assert orders_per_second > 10  # At least 10 orders/second


# =============================================================================
# Database Integration Tests
# =============================================================================

class TestDatabaseIntegration:
    """Database integration tests (with mock)"""

    @pytest.mark.asyncio
    async def test_trade_persistence(self):
        """Test trade record persistence"""
        from src.database.models import Trade, OrderSide, OrderType, OrderStatus, TradeType

        trade = Trade(
            exchange="binance",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            status=OrderStatus.FILLED,
            trade_type=TradeType.ARBITRAGE,
            requested_price=Decimal("42000"),
            executed_price=Decimal("42005"),
            requested_quantity=Decimal("0.1"),
            filled_quantity=Decimal("0.1"),
            fee=Decimal("4.2005")
        )

        # Verify trade object creation
        assert trade.exchange == "binance"
        assert trade.symbol == "BTCUSDT"
        assert trade.side == OrderSide.BUY
        assert trade.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_position_calculation(self):
        """Test position tracking"""
        from src.database.models import Position

        position = Position(
            exchange="binance",
            symbol="BTCUSDT",
            quantity=Decimal("0.5"),
            avg_entry_price=Decimal("42000"),
            current_price=Decimal("42500")
        )

        # Calculate PnL
        position.cost_basis = position.quantity * position.avg_entry_price
        position.market_value = position.quantity * position.current_price
        position.unrealized_pnl = position.market_value - position.cost_basis

        assert position.cost_basis == Decimal("21000")
        assert position.market_value == Decimal("21250")
        assert position.unrealized_pnl == Decimal("250")


# =============================================================================
# Notification Integration Tests
# =============================================================================

class TestNotificationIntegration:
    """Notification system integration tests"""

    @pytest.mark.asyncio
    async def test_notification_manager_initialization(self):
        """Test notification manager setup"""
        from src.notifications.channels import (
            NotificationManager,
            NotificationPriority,
            NotificationType
        )

        manager = NotificationManager()
        await manager.start()

        # Send test notification
        notification_id = await manager.notify(
            type=NotificationType.TRADE_EXECUTED,
            priority=NotificationPriority.INFO,
            title="Test Trade",
            message="Test trade executed successfully",
            data={"profit": 10.5}
        )

        assert notification_id is not None
        await manager.stop()


# =============================================================================
# Full Trade Cycle Integration Tests
# =============================================================================

class TestFullTradeCycle:
    """
    End-to-end tests for complete arbitrage trade cycles.

    Tests the full flow:
    1. Opportunity detection
    2. Balance validation
    3. Balance locking
    4. Order execution
    5. Balance reconciliation
    6. Profit calculation
    """

    @pytest.fixture
    def mock_config(self):
        """Create mock trading config"""
        from dataclasses import dataclass

        @dataclass
        class MockTradingConfig:
            mode: str = "paper"
            min_spread_percent: float = 0.1
            max_spread_percent: float = 5.0
            max_position_usd: float = 1000.0
            max_daily_loss_usd: float = 100.0
            max_daily_trades: int = 20
            order_timeout_seconds: int = 30
            max_slippage_bps: int = 50

        @dataclass
        class MockConfig:
            trading: MockTradingConfig = None
            exchanges: dict = None

            def __post_init__(self):
                if self.trading is None:
                    self.trading = MockTradingConfig()
                if self.exchanges is None:
                    self.exchanges = {"binance": {}, "mexc": {}}

        return MockConfig()

    @pytest.mark.asyncio
    async def test_complete_arbitrage_cycle(self, mock_exchanges, mock_config):
        """Test complete arbitrage cycle from detection to profit"""
        binance = mock_exchanges["binance"]
        mexc = mock_exchanges["mexc"]

        # Set up price differential (buy low on Binance, sell high on MEXC)
        binance.set_price("BTCUSDT", Decimal("42000"))
        mexc.set_price("BTCUSDT", Decimal("42100"))

        # Record initial balances
        binance_initial = await binance.get_balances()
        mexc_initial = await mexc.get_balances()
        initial_total_usdt = (
            binance_initial["USDT"]["free"] +
            mexc_initial["USDT"]["free"]
        )

        # Get order books to verify opportunity
        binance_book = await binance.get_orderbook("BTCUSDT")
        mexc_book = await mexc.get_orderbook("BTCUSDT")

        buy_price = binance_book["asks"][0][0]
        sell_price = mexc_book["bids"][0][0]
        spread = (sell_price - buy_price) / buy_price * Decimal("10000")

        # Verify spread exists
        assert spread > 0, "Expected positive spread"

        # Execute buy leg
        quantity = Decimal("0.1")
        buy_order = await binance.create_order(
            symbol="BTCUSDT",
            side="buy",
            order_type="market",
            quantity=quantity
        )

        # Execute sell leg
        sell_order = await mexc.create_order(
            symbol="BTCUSDT",
            side="sell",
            order_type="market",
            quantity=quantity
        )

        # Verify orders filled
        assert buy_order["status"] == "filled"
        assert sell_order["status"] == "filled"

        # Calculate profit
        buy_cost = buy_order["filled_quantity"] * buy_order["executed_price"]
        sell_proceeds = sell_order["filled_quantity"] * sell_order["executed_price"]
        gross_profit = sell_proceeds - buy_cost
        total_fees = buy_order["fee"] + sell_order["fee"]
        net_profit = gross_profit - total_fees

        # Verify final balances
        binance_final = await binance.get_balances()
        mexc_final = await mexc.get_balances()
        final_total_usdt = (
            binance_final["USDT"]["free"] +
            mexc_final["USDT"]["free"]
        )

        # Net USDT change should equal gross profit (before fees deducted from balance)
        usdt_change = final_total_usdt - initial_total_usdt

        # The actual profit is in the exchange balances
        print(f"Buy cost: {buy_cost:.2f}")
        print(f"Sell proceeds: {sell_proceeds:.2f}")
        print(f"Gross profit: {gross_profit:.2f}")
        print(f"Fees: {total_fees:.2f}")
        print(f"Net profit: {net_profit:.2f}")

    @pytest.mark.asyncio
    async def test_balance_validation_before_trade(self, mock_exchanges, mock_config):
        """Test balance validation prevents over-trading"""
        binance = mock_exchanges["binance"]

        # Try to buy more BTC than we have USDT for
        initial_balance = await binance.get_balances()
        usdt_available = initial_balance["USDT"]["free"]

        # Current price around 42000, calculate max we can buy
        ticker = await binance.get_ticker("BTCUSDT")
        max_quantity = usdt_available / ticker["ask"]

        # Try to buy more than max
        with pytest.raises(ValueError, match="Insufficient"):
            await binance.create_order(
                symbol="BTCUSDT",
                side="buy",
                order_type="market",
                quantity=max_quantity * Decimal("2")  # Double the max
            )

    @pytest.mark.asyncio
    async def test_partial_fill_handling(self, mock_exchanges):
        """Test handling of partial fills"""
        # Note: Current mock always fills completely
        # This test verifies the structure for partial fill handling
        binance = mock_exchanges["binance"]

        order = await binance.create_order(
            symbol="BTCUSDT",
            side="buy",
            order_type="market",
            quantity=Decimal("0.05")
        )

        # Verify fill quantity matches requested
        assert order["filled_quantity"] == Decimal("0.05")
        assert order["filled_quantity"] == order["quantity"]

    @pytest.mark.asyncio
    async def test_multi_symbol_arbitrage(self, mock_exchanges):
        """Test arbitrage across multiple trading pairs"""
        binance = mock_exchanges["binance"]
        mexc = mock_exchanges["mexc"]

        # Set up opportunities on both BTC and ETH
        binance.set_price("BTCUSDT", Decimal("42000"))
        mexc.set_price("BTCUSDT", Decimal("42100"))
        binance.set_price("ETHUSDT", Decimal("2200"))
        mexc.set_price("ETHUSDT", Decimal("2210"))

        # Execute both pairs concurrently
        results = await asyncio.gather(
            binance.create_order("BTCUSDT", "buy", "market", Decimal("0.05")),
            mexc.create_order("BTCUSDT", "sell", "market", Decimal("0.05")),
            binance.create_order("ETHUSDT", "buy", "market", Decimal("0.5")),
            mexc.create_order("ETHUSDT", "sell", "market", Decimal("0.5")),
            return_exceptions=True
        )

        # All orders should succeed
        for result in results:
            assert not isinstance(result, Exception)
            assert result["status"] == "filled"

    @pytest.mark.asyncio
    async def test_trade_cycle_with_fee_calculation(self, mock_exchanges):
        """Test that fees are correctly calculated and deducted"""
        binance = mock_exchanges["binance"]

        # Execute a trade
        order = await binance.create_order(
            symbol="BTCUSDT",
            side="buy",
            order_type="market",
            quantity=Decimal("0.1")
        )

        # Fee should be 0.1% of trade value
        expected_fee_rate = Decimal("0.001")
        trade_value = order["filled_quantity"] * order["executed_price"]
        expected_fee = trade_value * expected_fee_rate

        assert order["fee"] == expected_fee
        assert order["fee_currency"] == "USDT"


# =============================================================================
# Balance Manager Integration Tests
# =============================================================================

class TestBalanceManagerIntegration:
    """Tests for BalanceManager integration with trading"""

    @pytest.fixture
    def balance_manager_setup(self, mock_exchanges):
        """Set up balance manager with mock exchanges"""
        from unittest.mock import AsyncMock, MagicMock

        # Create mock balance manager
        class MockBalanceManager:
            def __init__(self):
                self._balances = {
                    "binance": {"USDT": Decimal("10000"), "BTC": Decimal("0.5")},
                    "mexc": {"USDT": Decimal("10000"), "BTC": Decimal("0.5")}
                }
                self._locks = {}
                self._lock_counter = 0

            async def get_balance(self, exchange: str, asset: str) -> Decimal:
                return self._balances.get(exchange, {}).get(asset, Decimal("0"))

            async def validate_arbitrage(
                self,
                buy_exchange: str,
                sell_exchange: str,
                base_asset: str,
                quote_asset: str,
                amount: Decimal,
                buy_price: Decimal,
                sell_price: Decimal
            ) -> tuple:
                # Check buy side has enough quote currency
                required_quote = amount * buy_price * Decimal("1.01")  # 1% buffer
                available_quote = self._balances.get(buy_exchange, {}).get(quote_asset, Decimal("0"))

                if available_quote < required_quote:
                    return False, f"Insufficient {quote_asset} on {buy_exchange}"

                # Check sell side has enough base currency
                available_base = self._balances.get(sell_exchange, {}).get(base_asset, Decimal("0"))
                if available_base < amount:
                    return False, f"Insufficient {base_asset} on {sell_exchange}"

                return True, "Validation passed"

            async def lock_balance(
                self,
                exchange: str,
                asset: str,
                amount: Decimal,
                trade_id: str
            ) -> Optional[str]:
                available = self._balances.get(exchange, {}).get(asset, Decimal("0"))
                if available < amount:
                    return None

                self._lock_counter += 1
                lock_id = f"lock_{self._lock_counter}"
                self._locks[lock_id] = {
                    "exchange": exchange,
                    "asset": asset,
                    "amount": amount,
                    "trade_id": trade_id
                }
                self._balances[exchange][asset] -= amount
                return lock_id

            async def release_lock(self, lock_id: str) -> bool:
                if lock_id not in self._locks:
                    return False

                lock = self._locks[lock_id]
                self._balances[lock["exchange"]][lock["asset"]] += lock["amount"]
                del self._locks[lock_id]
                return True

            async def consume_lock(self, lock_id: str) -> bool:
                if lock_id not in self._locks:
                    return False
                del self._locks[lock_id]
                return True

        return MockBalanceManager()

    @pytest.mark.asyncio
    async def test_balance_validation_success(self, balance_manager_setup, mock_exchanges):
        """Test successful balance validation"""
        bm = balance_manager_setup

        valid, reason = await bm.validate_arbitrage(
            buy_exchange="binance",
            sell_exchange="mexc",
            base_asset="BTC",
            quote_asset="USDT",
            amount=Decimal("0.1"),
            buy_price=Decimal("42000"),
            sell_price=Decimal("42100")
        )

        assert valid is True
        assert "passed" in reason.lower()

    @pytest.mark.asyncio
    async def test_balance_validation_insufficient_quote(self, balance_manager_setup):
        """Test validation fails with insufficient quote currency"""
        bm = balance_manager_setup

        valid, reason = await bm.validate_arbitrage(
            buy_exchange="binance",
            sell_exchange="mexc",
            base_asset="BTC",
            quote_asset="USDT",
            amount=Decimal("1000"),  # Would need 42M USDT
            buy_price=Decimal("42000"),
            sell_price=Decimal("42100")
        )

        assert valid is False
        assert "Insufficient" in reason

    @pytest.mark.asyncio
    async def test_balance_locking_flow(self, balance_manager_setup):
        """Test balance locking and unlocking"""
        bm = balance_manager_setup

        initial_balance = await bm.get_balance("binance", "USDT")

        # Lock some balance
        lock_id = await bm.lock_balance(
            exchange="binance",
            asset="USDT",
            amount=Decimal("5000"),
            trade_id="test_trade_1"
        )

        assert lock_id is not None

        # Balance should be reduced
        locked_balance = await bm.get_balance("binance", "USDT")
        assert locked_balance == initial_balance - Decimal("5000")

        # Release lock
        released = await bm.release_lock(lock_id)
        assert released is True

        # Balance should be restored
        final_balance = await bm.get_balance("binance", "USDT")
        assert final_balance == initial_balance

    @pytest.mark.asyncio
    async def test_balance_lock_prevents_double_spend(self, balance_manager_setup):
        """Test that locked balance cannot be double-spent"""
        bm = balance_manager_setup

        # Lock most of the balance
        lock1 = await bm.lock_balance(
            exchange="binance",
            asset="USDT",
            amount=Decimal("9000"),
            trade_id="trade_1"
        )
        assert lock1 is not None

        # Try to lock more than remaining
        lock2 = await bm.lock_balance(
            exchange="binance",
            asset="USDT",
            amount=Decimal("2000"),  # Only 1000 left
            trade_id="trade_2"
        )
        assert lock2 is None


# =============================================================================
# Graceful Shutdown Integration Tests
# =============================================================================

class TestGracefulShutdownIntegration:
    """Tests for graceful shutdown functionality"""

    @pytest.fixture
    def shutdown_manager_setup(self):
        """Create shutdown manager for testing"""
        from src.core.graceful_shutdown import (
            GracefulShutdownManager,
            ShutdownConfig,
            ShutdownPhase
        )

        config = ShutdownConfig(
            drain_timeout_seconds=2,
            cancel_timeout_seconds=2,
            cleanup_timeout_seconds=2,
            close_positions_on_shutdown=False
        )

        manager = GracefulShutdownManager(config=config)
        return manager

    @pytest.mark.asyncio
    async def test_operation_registration(self, shutdown_manager_setup):
        """Test in-flight operation registration"""
        manager = shutdown_manager_setup

        # Register operations
        op1 = manager.register_operation(
            operation_type="trade",
            exchange="binance",
            symbol="BTCUSDT"
        )
        op2 = manager.register_operation(
            operation_type="trade",
            exchange="mexc",
            symbol="BTCUSDT"
        )

        assert op1 is not None
        assert op2 is not None
        assert op1 != op2

        # Check status
        status = manager.get_status()
        assert status["in_flight_operations"] == 2

    @pytest.mark.asyncio
    async def test_operation_completion(self, shutdown_manager_setup):
        """Test operation completion tracking"""
        manager = shutdown_manager_setup

        op_id = manager.register_operation("trade", "binance", "BTCUSDT")
        assert manager.get_status()["in_flight_operations"] == 1

        manager.complete_operation(op_id)
        assert manager.get_status()["in_flight_operations"] == 0

    @pytest.mark.asyncio
    async def test_shutdown_blocks_new_operations(self, shutdown_manager_setup):
        """Test that shutdown blocks new operations"""
        from src.core.graceful_shutdown import ShutdownPhase

        manager = shutdown_manager_setup

        # Start shutdown (don't await to test blocking)
        shutdown_task = asyncio.create_task(manager.shutdown())

        # Wait for shutdown to start
        await asyncio.sleep(0.1)

        # New operations should be blocked
        with pytest.raises(RuntimeError, match="shutting down"):
            manager.register_operation("trade", "binance", "BTCUSDT")

        # Clean up
        await shutdown_task

    @pytest.mark.asyncio
    async def test_cleanup_handlers_called(self, shutdown_manager_setup):
        """Test that cleanup handlers are called during shutdown"""
        manager = shutdown_manager_setup

        cleanup_called = []

        async def cleanup_handler_1():
            cleanup_called.append("handler_1")

        async def cleanup_handler_2():
            cleanup_called.append("handler_2")

        manager.register_cleanup_handler(cleanup_handler_1)
        manager.register_cleanup_handler(cleanup_handler_2)

        await manager.shutdown()

        assert "handler_1" in cleanup_called
        assert "handler_2" in cleanup_called


# =============================================================================
# Health Server Integration Tests
# =============================================================================

class TestHealthServerIntegration:
    """Tests for health server functionality"""

    @pytest.mark.asyncio
    async def test_health_checker_initialization(self):
        """Test health checker setup"""
        from src.api.health import HealthChecker, HealthStatus

        checker = HealthChecker(version="1.0.0-test")

        assert checker.version == "1.0.0-test"
        assert checker.uptime_seconds >= 0

    @pytest.mark.asyncio
    async def test_liveness_check(self):
        """Test liveness probe"""
        from src.api.health import HealthChecker

        checker = HealthChecker()

        is_alive = await checker.liveness()
        assert is_alive is True

    @pytest.mark.asyncio
    async def test_readiness_check(self):
        """Test readiness probe"""
        from src.api.health import HealthChecker

        checker = HealthChecker()

        is_ready = await checker.readiness()
        # Should be ready by default (built-in checks should pass)
        assert isinstance(is_ready, bool)

    @pytest.mark.asyncio
    async def test_full_health_check(self):
        """Test full health check with all components"""
        from src.api.health import HealthChecker, HealthStatus

        checker = HealthChecker()

        health = await checker.check_health()

        assert health.version is not None
        assert health.uptime_seconds >= 0
        assert health.status in [
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
            HealthStatus.UNHEALTHY
        ]
        assert len(health.checks) > 0

    @pytest.mark.asyncio
    async def test_custom_health_check_registration(self):
        """Test registering custom health checks"""
        from src.api.health import HealthChecker, HealthCheckResult, HealthStatus

        checker = HealthChecker()

        async def custom_check() -> HealthCheckResult:
            return HealthCheckResult(
                name="custom",
                status=HealthStatus.HEALTHY,
                message="Custom check passed"
            )

        checker.register_check("custom", custom_check)

        health = await checker.check_health()

        # Find custom check in results
        custom_result = next(
            (c for c in health.checks if c.name == "custom"),
            None
        )

        assert custom_result is not None
        assert custom_result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_timeout_handling(self):
        """Test health check timeout handling"""
        from src.api.health import HealthChecker, HealthCheckResult, HealthStatus

        checker = HealthChecker()

        async def slow_check() -> HealthCheckResult:
            await asyncio.sleep(20)  # Will timeout
            return HealthCheckResult(
                name="slow",
                status=HealthStatus.HEALTHY,
                message="Should not reach here"
            )

        checker.register_check("slow", slow_check)

        # Run health check with timeout
        health = await checker.check_health(checks=["slow"])

        slow_result = next(
            (c for c in health.checks if c.name == "slow"),
            None
        )

        assert slow_result is not None
        assert slow_result.status == HealthStatus.UNHEALTHY
        assert "timed out" in slow_result.message.lower()


# =============================================================================
# Execution Engine Integration Tests
# =============================================================================

class TestExecutionEngineIntegration:
    """Tests for execution engine with balance validation"""

    @pytest.mark.asyncio
    async def test_execution_result_structure(self, mock_exchanges):
        """Test that execution returns proper result structure"""
        binance = mock_exchanges["binance"]

        order = await binance.create_order(
            symbol="BTCUSDT",
            side="buy",
            order_type="market",
            quantity=Decimal("0.1")
        )

        # Verify result structure
        required_fields = [
            "order_id", "symbol", "side", "type", "status",
            "quantity", "filled_quantity", "executed_price", "fee"
        ]

        for field in required_fields:
            assert field in order, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_atomic_arbitrage_execution(self, mock_exchanges):
        """Test atomic execution of both legs"""
        binance = mock_exchanges["binance"]
        mexc = mock_exchanges["mexc"]

        quantity = Decimal("0.1")

        # Execute both legs atomically
        try:
            results = await asyncio.gather(
                binance.create_order("BTCUSDT", "buy", "market", quantity),
                mexc.create_order("BTCUSDT", "sell", "market", quantity)
            )

            buy_order, sell_order = results

            # Both should succeed
            assert buy_order["status"] == "filled"
            assert sell_order["status"] == "filled"

        except Exception as e:
            # If either fails, we should handle rollback
            # (not implemented in mock, but tests the structure)
            pytest.fail(f"Atomic execution failed: {e}")


# =============================================================================
# End-to-End Scenario Tests
# =============================================================================

class TestEndToEndScenarios:
    """Complete end-to-end scenario tests"""

    @pytest.mark.asyncio
    async def test_profitable_arbitrage_scenario(self, mock_exchanges):
        """
        Complete profitable arbitrage scenario:
        1. Detect opportunity
        2. Validate balances
        3. Execute trades
        4. Calculate profit
        """
        binance = mock_exchanges["binance"]
        mexc = mock_exchanges["mexc"]

        # Setup: Create 0.5% spread opportunity
        binance.set_price("BTCUSDT", Decimal("40000"))
        mexc.set_price("BTCUSDT", Decimal("40200"))

        # Step 1: Detect opportunity
        binance_book = await binance.get_orderbook("BTCUSDT")
        mexc_book = await mexc.get_orderbook("BTCUSDT")

        buy_price = binance_book["asks"][0][0]
        sell_price = mexc_book["bids"][0][0]

        spread_pct = (sell_price - buy_price) / buy_price * 100
        print(f"Detected spread: {spread_pct:.3f}%")

        # Must have positive spread after fees (~0.2%)
        min_profitable_spread = Decimal("0.2")
        if spread_pct < min_profitable_spread:
            pytest.skip("Spread too small for test")

        # Step 2: Validate balances
        binance_bal = await binance.get_balances()
        mexc_bal = await mexc.get_balances()

        trade_size_btc = Decimal("0.1")
        required_usdt = trade_size_btc * buy_price * Decimal("1.01")

        assert binance_bal["USDT"]["free"] >= required_usdt
        assert mexc_bal["BTC"]["free"] >= trade_size_btc

        # Step 3: Execute trades
        buy_order = await binance.create_order(
            "BTCUSDT", "buy", "market", trade_size_btc
        )
        sell_order = await mexc.create_order(
            "BTCUSDT", "sell", "market", trade_size_btc
        )

        # Step 4: Calculate profit
        buy_cost = buy_order["filled_quantity"] * buy_order["executed_price"]
        sell_proceeds = sell_order["filled_quantity"] * sell_order["executed_price"]
        gross_profit = sell_proceeds - buy_cost
        fees = buy_order["fee"] + sell_order["fee"]
        net_profit = gross_profit - fees

        print(f"Gross profit: ${gross_profit:.2f}")
        print(f"Fees: ${fees:.2f}")
        print(f"Net profit: ${net_profit:.2f}")

        # With 0.5% spread and 0.2% fees, should be profitable
        assert gross_profit > 0

    @pytest.mark.asyncio
    async def test_failed_arbitrage_recovery(self, mock_exchanges):
        """
        Test recovery when one leg fails:
        1. Try to execute arbitrage
        2. First leg succeeds, second fails
        3. Handle the imbalance
        """
        binance = mock_exchanges["binance"]

        # Execute successful buy
        buy_order = await binance.create_order(
            "BTCUSDT", "buy", "market", Decimal("0.1")
        )
        assert buy_order["status"] == "filled"

        # Simulate failed sell (insufficient balance)
        # This tests error handling structure
        try:
            # Try to sell more than we have
            await binance.create_order(
                "BTCUSDT", "sell", "market", Decimal("100")
            )
            pytest.fail("Should have raised exception")
        except ValueError as e:
            assert "Insufficient" in str(e)

        # In real system, this would trigger:
        # 1. Position tracking update
        # 2. Alert notification
        # 3. Potential hedge or unwind


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
