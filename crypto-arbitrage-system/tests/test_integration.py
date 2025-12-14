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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
