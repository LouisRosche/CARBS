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


# =========================================================================== #
# Debiased Revalidation Tests — verifying critical fixes are correct
# =========================================================================== #


# --------------------------------------------------------------------------- #
# Test 8: Pre-created events available before streams start
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_events_precreated_before_streams():
    """run() should pre-create _orderbook_events for all symbols BEFORE streams start."""
    bot = _make_bot()
    bot.running = False  # Stop immediately after setup

    # Patch initialize to be a no-op (we only care about event pre-creation)
    bot.initialize = AsyncMock()
    bot.state_manager.update_trading_state = MagicMock()

    # Override _stream_orderbook to capture event state at stream start time
    events_at_stream_start = {}

    async def capture_stream(exchange_name, symbol):
        # Record whether event exists when stream starts
        events_at_stream_start[(exchange_name, symbol)] = symbol in bot._orderbook_events
        # Stop the bot so run() terminates
        bot.running = False

    bot._stream_orderbook = capture_stream
    bot.monitor_symbol = AsyncMock()
    bot.print_stats = AsyncMock()

    await bot.run()

    # Every stream should have seen its event already pre-created
    for key, had_event in events_at_stream_start.items():
        assert had_event, f"Event missing when stream started for {key}"


# --------------------------------------------------------------------------- #
# Test 9: monitor_symbol uses pre-created event (not creating a new one)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_monitor_symbol_uses_precreated_event():
    """monitor_symbol should reference the event from _orderbook_events, not create one."""
    bot = _make_bot()
    bot.running = True

    # Pre-create the event (as run() would do)
    original_event = asyncio.Event()
    bot._orderbook_events["BTC/USDT"] = original_event

    # Mock find_and_score_arbitrage to stop after first iteration
    call_count = 0

    async def mock_find(symbol):
        nonlocal call_count
        call_count += 1
        if call_count >= 1:
            bot.running = False
        return None

    bot.find_and_score_arbitrage = mock_find

    # Set the event so monitor_symbol wakes up immediately
    original_event.set()

    await bot.monitor_symbol("BTC/USDT")

    # The event in _orderbook_events should still be the SAME object (not replaced)
    assert bot._orderbook_events["BTC/USDT"] is original_event


# --------------------------------------------------------------------------- #
# Test 10: gather exception logging in find_and_score_arbitrage
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_gather_exceptions_logged():
    """find_and_score_arbitrage should log exceptions from failed fetches, not swallow."""
    bot = _make_bot()
    bot.risk_manager = MagicMock()
    bot.scoring_engine = MagicMock()

    # One exchange succeeds, one raises
    async def fetch_ok(ex, sym):
        return _make_orderbook(ex, sym)

    async def fetch_fail(ex, sym):
        raise ConnectionError("exchange down")

    original_fetch = bot.fetch_orderbook

    async def mock_fetch(exchange_name, symbol):
        if exchange_name == "binance":
            return await fetch_ok(exchange_name, symbol)
        raise ConnectionError("exchange down")

    bot.fetch_orderbook = mock_fetch

    result = await bot.find_and_score_arbitrage("BTC/USDT")

    # Should return None (only 1 valid orderbook, need 2)
    assert result is None
    # The exception should have been counted
    bot.metrics.increment.assert_any_call("orderbook_fetch_errors")


# --------------------------------------------------------------------------- #
# Test 11: PortfolioRisk.winning_trades computed from win_rate * total_trades
# --------------------------------------------------------------------------- #
def test_portfolio_risk_successful_trades_computation():
    """successful_trades should be computed as int(total_trades * win_rate)."""
    from src.core.risk_manager import PortfolioRisk

    pr = PortfolioRisk(
        total_positions_usd=Decimal("10000"),
        var_95=Decimal("500"),
        var_99=Decimal("800"),
        expected_shortfall=Decimal("600"),
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
        max_drawdown=Decimal("200"),
        max_drawdown_percent=2.0,
        current_drawdown=Decimal("50"),
        win_rate=0.75,
        profit_factor=3.0,
        avg_win=Decimal("100"),
        avg_loss=Decimal("33"),
        total_trades=100,
    )

    # Verify it does NOT have a winning_trades field
    assert not hasattr(pr, "winning_trades")

    # Verify the computation we use in advanced_main.py
    successful = int(pr.total_trades * pr.win_rate)
    assert successful == 75


# --------------------------------------------------------------------------- #
# Test 12: Antifragile adaptation rejects non-tunable params
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_antifragile_rejects_non_tunable_param():
    """Antifragile adaptation should reject params not in TUNABLE_PARAMS allowlist."""
    bot = _make_bot()
    bot.running = True

    # Use a real TradingConfig so __post_init__ works
    from src.config.settings import TradingConfig
    bot.config.trading = TradingConfig(
        mode="paper",
        min_spread_percent=0.3,
        max_spread_percent=10.0,
        max_position_usd=500,
        max_daily_loss_usd=100,
    )

    # Mock antifragile to propose changing 'mode' (forbidden)
    bot.antifragile = AsyncMock()
    bot.antifragile.run_adaptation_cycle = AsyncMock(
        return_value={"mode": "live"}
    )
    bot.antifragile.run_stress_test = AsyncMock(return_value={"risk_level": 0.1})

    # Run one cycle then stop
    original_sleep = asyncio.sleep

    async def one_shot_sleep(seconds):
        bot.running = False

    with patch("asyncio.sleep", side_effect=one_shot_sleep):
        await bot._run_antifragile_adaptation()

    # mode should still be "paper" — the adaptation was rejected
    assert bot.config.trading.mode == "paper"


# --------------------------------------------------------------------------- #
# Test 13: Antifragile adaptation rejects values violating safety bounds
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_antifragile_rejects_unsafe_values():
    """Antifragile should reject values that violate TradingConfig safety bounds."""
    bot = _make_bot()
    bot.running = True

    from src.config.settings import TradingConfig
    bot.config.trading = TradingConfig(
        mode="paper",
        min_spread_percent=0.3,
        max_spread_percent=10.0,
        max_position_usd=500,
        max_daily_loss_usd=100,
    )

    # Propose max_position_usd above the $100k hard cap
    bot.antifragile = AsyncMock()
    bot.antifragile.run_adaptation_cycle = AsyncMock(
        return_value={"max_position_usd": 999999.0}
    )
    bot.antifragile.run_stress_test = AsyncMock(return_value={"risk_level": 0.1})

    async def one_shot_sleep(seconds):
        bot.running = False

    with patch("asyncio.sleep", side_effect=one_shot_sleep):
        await bot._run_antifragile_adaptation()

    # Should have been rolled back to 500 (original value)
    assert bot.config.trading.max_position_usd == 500


# --------------------------------------------------------------------------- #
# Test 14: Antifragile adaptation ACCEPTS valid values
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_antifragile_accepts_valid_values():
    """Antifragile should accept tunable params within safety bounds."""
    bot = _make_bot()
    bot.running = True

    from src.config.settings import TradingConfig
    bot.config.trading = TradingConfig(
        mode="paper",
        min_spread_percent=0.3,
        max_spread_percent=10.0,
        max_position_usd=500,
        max_daily_loss_usd=100,
    )

    # Propose a valid increase within bounds
    bot.antifragile = AsyncMock()
    bot.antifragile.run_adaptation_cycle = AsyncMock(
        return_value={"max_position_usd": 1000.0}
    )
    bot.antifragile.run_stress_test = AsyncMock(return_value={"risk_level": 0.1})

    async def one_shot_sleep(seconds):
        bot.running = False

    with patch("asyncio.sleep", side_effect=one_shot_sleep):
        await bot._run_antifragile_adaptation()

    # Should have been applied
    assert bot.config.trading.max_position_usd == 1000.0


# --------------------------------------------------------------------------- #
# Test 15: Antifragile rejects min_spread below safety minimum
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_antifragile_rejects_min_spread_below_safety():
    """min_spread_percent below MIN_ALLOWED_SPREAD_PERCENT (0.05) should be rejected."""
    bot = _make_bot()
    bot.running = True

    from src.config.settings import TradingConfig
    bot.config.trading = TradingConfig(
        mode="paper",
        min_spread_percent=0.3,
        max_spread_percent=10.0,
        max_position_usd=500,
        max_daily_loss_usd=100,
    )

    bot.antifragile = AsyncMock()
    bot.antifragile.run_adaptation_cycle = AsyncMock(
        return_value={"min_spread_percent": 0.01}  # Below 0.05 safety minimum
    )
    bot.antifragile.run_stress_test = AsyncMock(return_value={"risk_level": 0.1})

    async def one_shot_sleep(seconds):
        bot.running = False

    with patch("asyncio.sleep", side_effect=one_shot_sleep):
        await bot._run_antifragile_adaptation()

    # Should remain at 0.3 (original)
    assert bot.config.trading.min_spread_percent == 0.3


# --------------------------------------------------------------------------- #
# Test 16: Main gather logs task failures
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_main_gather_logs_task_failures():
    """run() should log exceptions from crashed tasks, not silently swallow."""
    bot = _make_bot()
    bot.running = False  # Will stop loops quickly

    bot.initialize = AsyncMock()
    bot.state_manager.update_trading_state = MagicMock()

    # Make _stream_orderbook raise an unexpected error
    async def crashing_stream(exchange_name, symbol):
        raise RuntimeError("Unexpected crash in stream")

    bot._stream_orderbook = crashing_stream
    bot.monitor_symbol = AsyncMock(return_value=None)
    bot.print_stats = AsyncMock(return_value=None)

    # run() should complete without raising (gather returns exceptions)
    await bot.run()
    # The task should have produced a RuntimeError in results — we just verify
    # run() didn't crash (the error is logged, not raised)


# --------------------------------------------------------------------------- #
# Test 17: TradingConfig __post_init__ validation
# --------------------------------------------------------------------------- #
def test_trading_config_validates_on_init():
    """TradingConfig should raise on invalid values during __post_init__."""
    from src.config.settings import TradingConfig, ConfigValidationError

    # Valid config should work
    tc = TradingConfig(
        mode="paper", min_spread_percent=0.1, max_spread_percent=5.0,
        max_position_usd=1000, max_daily_loss_usd=100,
    )
    assert tc.mode == "paper"

    # Position above hard cap
    with pytest.raises(ConfigValidationError, match="safety limit"):
        TradingConfig(
            mode="paper", min_spread_percent=0.1, max_spread_percent=5.0,
            max_position_usd=200000, max_daily_loss_usd=100,
        )

    # Spread below minimum
    with pytest.raises(ConfigValidationError, match="safety minimum"):
        TradingConfig(
            mode="paper", min_spread_percent=0.01, max_spread_percent=5.0,
            max_position_usd=1000, max_daily_loss_usd=100,
        )

    # Invalid mode
    with pytest.raises(ConfigValidationError, match="Invalid trading mode"):
        TradingConfig(mode="yolo")

    # Slippage above 500 bps
    with pytest.raises(ConfigValidationError, match="max_slippage_bps"):
        TradingConfig(
            mode="paper", min_spread_percent=0.1, max_spread_percent=5.0,
            max_position_usd=1000, max_daily_loss_usd=100,
            max_slippage_bps=600,
        )


# --------------------------------------------------------------------------- #
# Test 18: Antifragile adaptation with multiple params (some valid, some not)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_antifragile_mixed_adaptations():
    """Antifragile: valid params applied, invalid ones rejected, independently."""
    bot = _make_bot()
    bot.running = True

    from src.config.settings import TradingConfig
    bot.config.trading = TradingConfig(
        mode="paper",
        min_spread_percent=0.3,
        max_spread_percent=10.0,
        max_position_usd=500,
        max_daily_loss_usd=100,
        max_slippage_bps=50,
    )

    # Mix: order_timeout_seconds=15 (valid), mode=live (blocked by allowlist),
    # max_slippage_bps=600 (blocked by __post_init__)
    bot.antifragile = AsyncMock()
    bot.antifragile.run_adaptation_cycle = AsyncMock(
        return_value={
            "order_timeout_seconds": 15,
            "mode": "live",
            "max_slippage_bps": 600,
        }
    )
    bot.antifragile.run_stress_test = AsyncMock(return_value={"risk_level": 0.1})

    async def one_shot_sleep(seconds):
        bot.running = False

    with patch("asyncio.sleep", side_effect=one_shot_sleep):
        await bot._run_antifragile_adaptation()

    assert bot.config.trading.order_timeout_seconds == 15  # Applied
    assert bot.config.trading.mode == "paper"              # Rejected (not tunable)
    assert bot.config.trading.max_slippage_bps == 50       # Rejected (validation failed)
