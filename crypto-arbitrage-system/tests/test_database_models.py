"""
Tests for database models and repository layer.

Tests verify:
- Data model instantiation and defaults
- Schema SQL validity
- Repository CRUD operations (mocked DB)
- DatabaseManager initialization
"""

import pytest
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.database.models import (
    Trade, ArbitrageExecution, Position, BalanceSnapshot, DailyPnL,
    OrderSide, OrderType, OrderStatus, TradeType,
    TradeRepository, ArbitrageRepository, PositionRepository, BalanceRepository,
    DatabaseManager, SCHEMA_SQL,
)


# === Data Model Tests ===


class TestTradeModel:
    """Test Trade dataclass defaults and construction"""

    def test_default_values(self):
        trade = Trade()
        assert trade.id is None
        assert trade.exchange == ""
        assert trade.side == OrderSide.BUY
        assert trade.order_type == OrderType.LIMIT
        assert trade.status == OrderStatus.PENDING
        assert trade.trade_type == TradeType.ARBITRAGE
        assert trade.requested_price == Decimal("0")
        assert trade.filled_quantity == Decimal("0")
        assert trade.fee == Decimal("0")
        assert trade.metadata == {}

    def test_custom_values(self):
        trade = Trade(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            requested_price=Decimal("67000.50"),
            requested_quantity=Decimal("0.1"),
        )
        assert trade.exchange == "binance"
        assert trade.symbol == "BTC/USDT"
        assert trade.side == OrderSide.SELL
        assert trade.requested_price == Decimal("67000.50")

    def test_metadata_isolation(self):
        """Each Trade instance should have its own metadata dict"""
        t1 = Trade()
        t2 = Trade()
        t1.metadata["key"] = "value"
        assert "key" not in t2.metadata


class TestArbitrageExecutionModel:
    def test_default_values(self):
        ae = ArbitrageExecution()
        assert ae.success is False
        assert ae.buy_price == Decimal("0")
        assert ae.quantity == Decimal("0")
        assert ae.metadata == {}

    def test_custom_values(self):
        ae = ArbitrageExecution(
            symbol="ETH/USDT",
            buy_exchange="binance",
            sell_exchange="mexc",
            buy_price=Decimal("2200"),
            sell_price=Decimal("2205"),
            spread_bps=Decimal("22.73"),
            net_profit=Decimal("3.50"),
            success=True,
        )
        assert ae.symbol == "ETH/USDT"
        assert ae.success is True
        assert ae.net_profit == Decimal("3.50")


class TestPositionModel:
    def test_default_values(self):
        pos = Position()
        assert pos.quantity == Decimal("0")
        assert pos.realized_pnl == Decimal("0")

    def test_custom_position(self):
        pos = Position(
            exchange="binance",
            symbol="BTC/USDT",
            quantity=Decimal("0.5"),
            avg_entry_price=Decimal("42000"),
            cost_basis=Decimal("21000"),
        )
        assert pos.exchange == "binance"
        assert pos.cost_basis == Decimal("21000")


class TestBalanceSnapshotModel:
    def test_default_values(self):
        bs = BalanceSnapshot()
        assert bs.total == Decimal("0")
        assert bs.available == Decimal("0")
        assert bs.locked == Decimal("0")


class TestDailyPnLModel:
    def test_default_values(self):
        d = DailyPnL()
        assert d.total_trades == 0
        assert d.gross_pnl == Decimal("0")
        assert d.net_pnl == Decimal("0")


class TestEnumValues:
    def test_order_side_values(self):
        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"

    def test_order_type_values(self):
        assert OrderType.MARKET.value == "market"
        assert OrderType.STOP_LIMIT.value == "stop_limit"

    def test_order_status_values(self):
        assert OrderStatus.PENDING.value == "pending"
        assert OrderStatus.FILLED.value == "filled"
        assert OrderStatus.CANCELLED.value == "cancelled"

    def test_trade_type_values(self):
        assert TradeType.ARBITRAGE.value == "arbitrage"
        assert TradeType.EMERGENCY_CLOSE.value == "emergency_close"


# === Schema SQL Tests ===


class TestSchemaSql:
    def test_schema_contains_required_tables(self):
        for table in [
            "trades", "arbitrage_executions", "positions",
            "balance_snapshots", "daily_pnl", "opportunities", "audit_log"
        ]:
            assert f"CREATE TABLE IF NOT EXISTS {table}" in SCHEMA_SQL

    def test_schema_contains_indexes(self):
        assert "CREATE INDEX" in SCHEMA_SQL
        assert "idx_trades_exchange_symbol" in SCHEMA_SQL
        assert "idx_arbitrage_created_at" in SCHEMA_SQL

    def test_schema_contains_enum_types(self):
        assert "order_side" in SCHEMA_SQL
        assert "order_status" in SCHEMA_SQL
        assert "trade_type" in SCHEMA_SQL

    def test_schema_contains_update_trigger(self):
        assert "update_updated_at_column" in SCHEMA_SQL

    def test_schema_uses_decimal_for_prices(self):
        """All monetary columns should use DECIMAL(24, 8) for precision"""
        assert "DECIMAL(24, 8)" in SCHEMA_SQL


# === Repository Tests (mocked DB) ===


class TestTradeRepository:
    @pytest.fixture
    def mock_pool(self):
        conn = AsyncMock()
        pool = MagicMock()

        @asynccontextmanager
        async def _acquire():
            yield conn

        pool.acquire = _acquire
        return pool, conn

    @pytest.fixture
    def repo(self, mock_pool):
        pool, _ = mock_pool
        return TradeRepository(pool)

    async def test_create_trade(self, mock_pool, repo):
        _, conn = mock_pool
        conn.fetchrow.return_value = {"id": "abc-123"}
        trade = Trade(
            exchange="binance",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            requested_price=Decimal("67000"),
            requested_quantity=Decimal("0.1"),
        )
        result = await repo.create(trade)
        assert result == "abc-123"
        conn.fetchrow.assert_called_once()

    async def test_update_status(self, mock_pool, repo):
        _, conn = mock_pool
        await repo.update_status("abc-123", OrderStatus.FILLED, Decimal("0.1"))
        conn.execute.assert_called_once()

    async def test_get_by_id_found(self, mock_pool, repo):
        _, conn = mock_pool
        conn.fetchrow.return_value = {
            "id": "abc-123", "external_id": None, "exchange": "binance",
            "symbol": "BTC/USDT", "side": "buy", "order_type": "limit",
            "status": "filled", "trade_type": "arbitrage",
            "requested_price": Decimal("67000"), "executed_price": Decimal("67000"),
            "slippage_bps": Decimal("0"), "requested_quantity": Decimal("0.1"),
            "filled_quantity": Decimal("0.1"), "fee": Decimal("6.70"),
            "fee_currency": "USDT", "gross_pnl": Decimal("15"),
            "net_pnl": Decimal("8.30"), "execution_time_ms": 200,
            "created_at": datetime.now(timezone.utc),
            "submitted_at": None, "filled_at": None,
            "updated_at": datetime.now(timezone.utc),
            "client_order_id": None, "notes": None, "metadata": {},
        }
        trade = await repo.get_by_id("abc-123")
        assert trade is not None
        assert trade.exchange == "binance"
        assert trade.side == OrderSide.BUY

    async def test_get_by_id_not_found(self, mock_pool, repo):
        _, conn = mock_pool
        conn.fetchrow.return_value = None
        trade = await repo.get_by_id("nonexistent")
        assert trade is None

    async def test_get_recent_with_filters(self, mock_pool, repo):
        _, conn = mock_pool
        conn.fetch.return_value = []
        result = await repo.get_recent(exchange="binance", symbol="BTC/USDT", limit=10)
        assert result == []
        call_args = conn.fetch.call_args
        query = call_args[0][0]
        assert "exchange" in query
        assert "symbol" in query


class TestArbitrageRepository:
    @pytest.fixture
    def mock_pool(self):
        conn = AsyncMock()
        pool = MagicMock()

        @asynccontextmanager
        async def _acquire():
            yield conn

        pool.acquire = _acquire
        return pool, conn

    async def test_create_execution(self, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = {"id": "exec-001"}
        repo = ArbitrageRepository(pool)
        execution = ArbitrageExecution(
            symbol="BTC/USDT",
            buy_exchange="binance",
            sell_exchange="mexc",
            buy_price=Decimal("67000"),
            sell_price=Decimal("67150"),
            spread_bps=Decimal("22.39"),
            quantity=Decimal("0.1"),
            net_profit=Decimal("8.30"),
            success=True,
        )
        result = await repo.create(execution)
        assert result == "exec-001"

    async def test_get_performance_stats(self, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = {
            "total_executions": 100, "successful": 95, "failed": 5,
            "total_profit": Decimal("500"), "avg_profit": Decimal("5.26"),
            "avg_spread_bps": Decimal("15.5"), "avg_execution_time": 250,
        }
        repo = ArbitrageRepository(pool)
        stats = await repo.get_performance_stats(days=30)
        assert stats["total_executions"] == 100
        assert stats["successful"] == 95


class TestPositionRepository:
    @pytest.fixture
    def mock_pool(self):
        conn = AsyncMock()
        pool = MagicMock()

        @asynccontextmanager
        async def _acquire():
            yield conn

        pool.acquire = _acquire
        return pool, conn

    async def test_upsert(self, mock_pool):
        pool, conn = mock_pool
        repo = PositionRepository(pool)
        pos = Position(
            exchange="binance", symbol="BTC/USDT",
            quantity=Decimal("0.5"),
        )
        await repo.upsert(pos)
        conn.execute.assert_called_once()
        query = conn.execute.call_args[0][0]
        assert "ON CONFLICT" in query

    async def test_get_total_value(self, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = {"total": Decimal("50000")}
        repo = PositionRepository(pool)
        total = await repo.get_total_value()
        assert total == Decimal("50000")


class TestBalanceRepository:
    @pytest.fixture
    def mock_pool(self):
        conn = AsyncMock()
        pool = MagicMock()

        @asynccontextmanager
        async def _acquire():
            yield conn

        pool.acquire = _acquire
        return pool, conn

    async def test_snapshot(self, mock_pool):
        pool, conn = mock_pool
        repo = BalanceRepository(pool)
        bs = BalanceSnapshot(
            exchange="binance", currency="USDT",
            total=Decimal("10000"), available=Decimal("9500"),
            locked=Decimal("500"),
        )
        await repo.snapshot(bs)
        conn.execute.assert_called_once()

    async def test_get_latest_found(self, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = {
            "id": "snap-001", "exchange": "binance", "currency": "USDT",
            "total": Decimal("10000"), "available": Decimal("9500"),
            "locked": Decimal("500"), "usd_value": Decimal("10000"),
            "snapshot_at": datetime.now(timezone.utc),
        }
        repo = BalanceRepository(pool)
        result = await repo.get_latest("binance", "USDT")
        assert result is not None
        assert result.total == Decimal("10000")

    async def test_get_latest_not_found(self, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = None
        repo = BalanceRepository(pool)
        result = await repo.get_latest("binance", "USDT")
        assert result is None


# === DatabaseManager Tests ===


class TestDatabaseManager:
    @pytest.fixture
    def mock_pool(self):
        conn = AsyncMock()
        pool = MagicMock()

        @asynccontextmanager
        async def _acquire():
            yield conn

        pool.acquire = _acquire
        return pool, conn

    def test_initialization(self, mock_pool):
        pool, _ = mock_pool
        dm = DatabaseManager(pool)
        assert isinstance(dm.trades, TradeRepository)
        assert isinstance(dm.arbitrage, ArbitrageRepository)
        assert isinstance(dm.positions, PositionRepository)
        assert isinstance(dm.balances, BalanceRepository)

    async def test_initialize_schema(self, mock_pool):
        pool, conn = mock_pool
        dm = DatabaseManager(pool)
        await dm.initialize_schema()
        conn.execute.assert_called_once_with(SCHEMA_SQL)

    async def test_health_check_healthy(self, mock_pool):
        pool, conn = mock_pool
        conn.fetchval.return_value = 1
        dm = DatabaseManager(pool)
        assert await dm.health_check() is True

    async def test_health_check_unhealthy(self, mock_pool):
        pool, conn = mock_pool
        conn.fetchval.side_effect = Exception("Connection lost")
        dm = DatabaseManager(pool)
        assert await dm.health_check() is False
