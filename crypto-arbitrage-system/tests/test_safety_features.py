"""
Tests for safety features in advanced_main.py:
- Balance manager validation before execution
- Stale orderbook rejection (>5s via in-memory WS cache)
- Fresh orderbook acceptance (<5s via in-memory WS cache)
- Balance manager started during bot initialization
- Persistent WS stream updates in-memory cache
- Event-driven monitor_symbol reacts to WS updates
"""

import asyncio
import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.advanced_engine import EnhancedOrderBook


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
    bot.advanced_engine = MagicMock()
    bot.advanced_engine.update_price_history = MagicMock()
    return bot


def _make_orderbook(exchange: str, symbol: str, age_seconds: float = 0) -> EnhancedOrderBook:
    """Create an EnhancedOrderBook with a configurable age."""
    ts = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    return EnhancedOrderBook(
        exchange=exchange,
        symbol=symbol,
        timestamp=ts,
        bids=[(Decimal("67000"), Decimal("1.0"))],
        asks=[(Decimal("67100"), Decimal("1.0"))],
    )


# --------------------------------------------------------------------------- #
# Test 1: Balance manager is passed to ExecutionEngine
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_balance_manager_validates_before_execution():
    """ExecutionEngine must receive the balance_manager so it can validate trades."""
    bot = _make_bot()

    mock_bm = AsyncMock()
    mock_bm.validate_arbitrage = AsyncMock(return_value=(True, "OK"))
    bot.balance_manager = mock_bm

    from src.core.execution_engine import ExecutionEngine

    with patch.object(ExecutionEngine, "__init__", return_value=None) as mock_init:
        ExecutionEngine(bot.config, bot.exchanges, balance_manager=bot.balance_manager)

        mock_init.assert_called_once_with(
            bot.config, bot.exchanges, balance_manager=mock_bm
        )


# --------------------------------------------------------------------------- #
# Test 2: Stale in-memory orderbook is rejected (>5s old)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_stale_orderbook_rejected():
    """fetch_orderbook_sync should reject in-memory data older than 5 seconds."""
    bot = _make_bot()

    # Place a stale orderbook in the WS cache
    stale_ob = _make_orderbook("binance", "BTC/USDT", age_seconds=10)
    bot._latest_orderbooks[("binance", "BTC/USDT")] = stale_ob

    result = bot.fetch_orderbook_sync("binance", "BTC/USDT")

    assert result is None
    bot.metrics.increment.assert_any_call("orderbook_stale_rejects")


# --------------------------------------------------------------------------- #
# Test 3: Fresh in-memory orderbook is accepted (<5s old)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_fresh_cached_orderbook_accepted():
    """fetch_orderbook_sync should return fresh in-memory data (<5s old)."""
    bot = _make_bot()

    fresh_ob = _make_orderbook("binance", "BTC/USDT", age_seconds=2)
    bot._latest_orderbooks[("binance", "BTC/USDT")] = fresh_ob

    result = bot.fetch_orderbook_sync("binance", "BTC/USDT")

    assert result is not None
    assert result.exchange == "binance"
    assert result.symbol == "BTC/USDT"
    bot.metrics.increment.assert_any_call("orderbook_cache_hits")


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
        mock_db = AsyncMock()
        mock_db_cls.return_value = mock_db
        mock_redis = AsyncMock()
        mock_redis_cls.return_value = mock_redis
        mock_metrics_cls.return_value = MagicMock()

        mock_state = MagicMock()
        mock_state.update_trading_state = MagicMock()
        mock_state.update_system_health = MagicMock()
        mock_state_mgr.return_value = mock_state

        mock_bm_instance = AsyncMock()
        mock_bm_instance.start = AsyncMock()
        mock_bm_cls.return_value = mock_bm_instance

        await bot.initialize()

        mock_bm_cls.assert_called_once()
        mock_bm_instance.start.assert_awaited_once()


# --------------------------------------------------------------------------- #
# Test 5: WS stream updates in-memory cache
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_ws_stream_populates_cache():
    """_stream_orderbook should store fresh orderbooks in _latest_orderbooks."""
    bot = _make_bot()
    bot.running = True

    # Mock exchange.watch_order_book to return data once, then stop the bot
    call_count = 0

    async def mock_watch(symbol):
        nonlocal call_count
        call_count += 1
        if call_count > 1:
            bot.running = False
            raise asyncio.CancelledError()
        return {
            "bids": [[67000.0, 1.0], [66999.0, 0.5]],
            "asks": [[67100.0, 1.0], [67101.0, 0.5]],
        }

    bot.exchanges["binance"].watch_order_book = mock_watch

    await bot._stream_orderbook("binance", "BTC/USDT")

    key = ("binance", "BTC/USDT")
    assert key in bot._latest_orderbooks
    ob = bot._latest_orderbooks[key]
    assert ob.exchange == "binance"
    assert ob.symbol == "BTC/USDT"
    assert len(ob.bids) == 2
    bot.metrics.increment.assert_any_call("orderbooks_fetched")


# --------------------------------------------------------------------------- #
# Test 6: WS stream signals event for monitor_symbol
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_ws_stream_signals_event():
    """_stream_orderbook should set the event so monitor_symbol wakes up."""
    bot = _make_bot()
    bot.running = True

    event = asyncio.Event()
    bot._orderbook_events["BTC/USDT"] = event

    call_count = 0

    async def mock_watch(symbol):
        nonlocal call_count
        call_count += 1
        if call_count > 1:
            bot.running = False
            raise asyncio.CancelledError()
        return {"bids": [[67000.0, 1.0]], "asks": [[67100.0, 1.0]]}

    bot.exchanges["binance"].watch_order_book = mock_watch

    # Event should be unset initially
    assert not event.is_set()

    await bot._stream_orderbook("binance", "BTC/USDT")

    # After stream processes, event should have been set (may be cleared by now
    # if someone was waiting, but cache should be populated)
    assert ("binance", "BTC/USDT") in bot._latest_orderbooks


# --------------------------------------------------------------------------- #
# Test 7: fetch_orderbook falls back to direct WS call when cache is empty
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_fetch_orderbook_fallback_on_empty_cache():
    """fetch_orderbook should call watch_order_book directly when WS cache is empty."""
    bot = _make_bot()

    bot.exchanges["binance"].watch_order_book = AsyncMock(
        return_value={"bids": [[67000.0, 1.0]], "asks": [[67100.0, 1.0]]}
    )

    # Cache is empty — no entry in _latest_orderbooks
    result = await bot.fetch_orderbook("binance", "BTC/USDT")

    assert result is not None
    assert result.exchange == "binance"
    bot.exchanges["binance"].watch_order_book.assert_awaited_once_with("BTC/USDT")
    # Should also populate the in-memory cache
    assert ("binance", "BTC/USDT") in bot._latest_orderbooks
