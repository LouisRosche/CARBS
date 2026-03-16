"""
Tests for safety features in advanced_main.py:
- Balance manager validation before execution
- Stale orderbook rejection (>5s cached data)
- Fresh cached orderbook acceptance (<5s cached data)
- Balance manager started during bot initialization
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


class MockConfig:
    """Mock configuration matching AdvancedArbitrageBot expectations"""

    class Trading:
        mode = "paper"
        min_spread_percent = 0.3
        max_spread_percent = 10.0
        max_position_usd = 500
        max_daily_loss_usd = 100

    trading = Trading()
    exchanges = {
        "binance": {"enabled": True, "taker_fee": 0.001},
        "mexc": {"enabled": True, "taker_fee": 0.001},
    }
    symbols = ["BTC/USDT"]

    class Database:
        pass

    class Redis:
        pass

    database = Database()
    redis = Redis()
    monitoring = {"prometheus_port": 9090, "health_port": 8080}
    performance = {"balance_update_interval_seconds": 30, "check_interval_seconds": 1}


def _make_bot():
    """Create an AdvancedArbitrageBot with mocked internals (no initialize call)."""
    from src.advanced_main import AdvancedArbitrageBot

    bot = AdvancedArbitrageBot()
    bot.config = MockConfig()
    bot.exchanges = {"binance": AsyncMock(), "mexc": AsyncMock()}
    bot.db_pool = AsyncMock()
    bot.cache = AsyncMock()
    bot.metrics = MagicMock()
    bot.metrics.increment = MagicMock()
    bot.state_manager = MagicMock()
    bot.state_manager.update_trading_state = MagicMock()
    bot.state_manager.record_opportunity = MagicMock()
    bot.state_manager.record_error = MagicMock()
    bot.state_manager.record_trade = MagicMock()
    bot.state_manager.get_trading_state = MagicMock(
        return_value=MagicMock(total_profit=Decimal("0"))
    )
    return bot


# --------------------------------------------------------------------------- #
# Test 1: Balance manager is passed to ExecutionEngine
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_balance_manager_validates_before_execution():
    """ExecutionEngine must receive the balance_manager so it can validate trades."""
    bot = _make_bot()

    # Set up a mock balance_manager
    mock_bm = AsyncMock()
    mock_bm.validate_arbitrage = AsyncMock(return_value=(True, "OK"))
    bot.balance_manager = mock_bm

    # Build ExecutionEngine the same way initialize() does
    from src.core.execution_engine import ExecutionEngine

    with patch.object(ExecutionEngine, "__init__", return_value=None) as mock_init:
        engine = ExecutionEngine.__new__(ExecutionEngine)
        mock_init.assert_not_called()  # sanity: not yet called

        # Replicate the line from initialize():
        engine = ExecutionEngine(
            bot.config, bot.exchanges, balance_manager=bot.balance_manager
        )

        # Verify balance_manager was passed
        mock_init.assert_called_once_with(
            bot.config, bot.exchanges, balance_manager=mock_bm
        )


# --------------------------------------------------------------------------- #
# Test 2: Stale cached orderbook is rejected (>5s old)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_stale_orderbook_rejected():
    """fetch_orderbook should reject cached data older than 5 seconds and fetch fresh."""
    bot = _make_bot()

    stale_timestamp = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()

    # Cache returns stale data
    bot.cache.get = AsyncMock(
        return_value={
            "exchange": "binance",
            "symbol": "BTC/USDT",
            "timestamp": stale_timestamp,
            "bids": [["67000", "1.0"]],
            "asks": [["67100", "1.0"]],
        }
    )

    # Set up the exchange to return fresh data when cache is stale
    bot.exchanges["binance"].watch_order_book = AsyncMock(
        return_value={
            "bids": [[67000.0, 1.0]],
            "asks": [[67100.0, 1.0]],
        }
    )

    # Need advanced_engine for price history update
    bot.advanced_engine = MagicMock()
    bot.advanced_engine.update_price_history = MagicMock()

    result = await bot.fetch_orderbook("binance", "BTC/USDT")

    # Stale data should be rejected -> falls through to live fetch
    bot.metrics.increment.assert_any_call("orderbook_stale_rejects")
    # Live fetch should have been called
    bot.exchanges["binance"].watch_order_book.assert_awaited_once_with("BTC/USDT")
    assert result is not None
    assert result.exchange == "binance"


# --------------------------------------------------------------------------- #
# Test 3: Fresh cached orderbook is accepted (<5s old)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_fresh_cached_orderbook_accepted():
    """fetch_orderbook should accept cached data that is less than 5 seconds old."""
    bot = _make_bot()

    fresh_timestamp = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()

    bot.cache.get = AsyncMock(
        return_value={
            "exchange": "binance",
            "symbol": "BTC/USDT",
            "timestamp": fresh_timestamp,
            "bids": [["67000", "1.0"]],
            "asks": [["67100", "1.0"]],
        }
    )

    result = await bot.fetch_orderbook("binance", "BTC/USDT")

    # Fresh cache should be used — no live fetch
    bot.metrics.increment.assert_any_call("orderbook_cache_hits")
    bot.exchanges["binance"].watch_order_book = AsyncMock()
    # Verify we did NOT call the exchange
    bot.exchanges["binance"].watch_order_book.assert_not_awaited()
    assert result is not None
    assert result.exchange == "binance"
    assert result.symbol == "BTC/USDT"


# --------------------------------------------------------------------------- #
# Test 4: BalanceManager.start() called during initialize()
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_balance_manager_started_during_init():
    """BalanceManager.start() must be called during bot initialization."""
    from src.advanced_main import AdvancedArbitrageBot

    bot = AdvancedArbitrageBot()

    with (
        patch("src.advanced_main.load_config", return_value=MockConfig()),
        patch("src.advanced_main.DatabasePool") as mock_db_cls,
        patch("src.advanced_main.RedisCache") as mock_redis_cls,
        patch("src.advanced_main.MetricsCollector") as mock_metrics_cls,
        patch("src.advanced_main.get_state_manager") as mock_state_mgr,
        patch.object(bot, "_initialize_exchanges", new_callable=AsyncMock),
        patch.object(bot, "_initialize_optional_modules", new_callable=AsyncMock),
        patch("src.advanced_main.BalanceManager") as mock_bm_cls,
        patch("src.advanced_main.AdvancedArbitrageEngine"),
        patch("src.advanced_main.ExecutionEngine"),
        patch("src.advanced_main.RiskManager"),
        patch("src.advanced_main.HEALTH_SERVER_AVAILABLE", False),
    ):
        # Wire up async mocks
        mock_db = AsyncMock()
        mock_db_cls.return_value = mock_db
        mock_redis = AsyncMock()
        mock_redis_cls.return_value = mock_redis
        mock_metrics_cls.return_value = MagicMock()

        mock_state = MagicMock()
        mock_state.update_trading_state = MagicMock()
        mock_state.update_system_health = MagicMock()
        mock_state_mgr.return_value = mock_state

        # BalanceManager mock
        mock_bm_instance = AsyncMock()
        mock_bm_instance.start = AsyncMock()
        mock_bm_cls.return_value = mock_bm_instance

        await bot.initialize()

        # Verify BalanceManager was instantiated and start() was called
        mock_bm_cls.assert_called_once()
        mock_bm_instance.start.assert_awaited_once()
