"""
End-to-end tests for the arbitrage detection pipeline.

Tests the full flow from orderbook fetching through opportunity detection,
using mocked exchange connections, database, Redis cache, and metrics.
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.engine import ArbitrageEngine, Opportunity, OrderBook
from src.config.settings import Config, TradingConfig


def _make_config(
    min_spread_percent: float = 0.1,
    max_spread_percent: float = 5.0,
    max_position_usd: float = 1000.0,
) -> Config:
    """Build a minimal Config object suitable for ArbitrageEngine."""
    return Config(
        trading=TradingConfig(
            mode="paper",
            min_spread_percent=min_spread_percent,
            max_spread_percent=max_spread_percent,
            max_position_usd=max_position_usd,
        ),
        exchanges={
            "exchange_a": {"enabled": True, "taker_fee": 0.001},
            "exchange_b": {"enabled": True, "taker_fee": 0.001},
        },
        symbols=["BTC/USDT"],
    )


def _make_mock_exchange(orderbook_data: dict) -> AsyncMock:
    """Create a mock ccxt.pro exchange that returns the given orderbook."""
    exchange = AsyncMock()
    exchange.watch_order_book = AsyncMock(return_value=orderbook_data)
    exchange.load_markets = AsyncMock(return_value={})
    exchange.fees = {"trading": {"taker": 0.001, "maker": 0.001}}
    exchange.close = AsyncMock()
    return exchange


@pytest.fixture
def engine_with_spread():
    """
    ArbitrageEngine wired with two mock exchanges whose orderbooks
    have a profitable spread (~0.45%):
      - exchange_a: best ask 67000
      - exchange_b: best bid 67300
    """
    config = _make_config()
    engine = ArbitrageEngine(config)

    ob_a = {
        "bids": [[66900, 2.0], [66800, 3.0]],
        "asks": [[67000, 2.0], [67100, 3.0]],
    }
    ob_b = {
        "bids": [[67300, 2.0], [67200, 3.0]],
        "asks": [[67400, 2.0], [67500, 3.0]],
    }

    engine.exchanges = {
        "exchange_a": _make_mock_exchange(ob_a),
        "exchange_b": _make_mock_exchange(ob_b),
    }

    # Stub out infrastructure dependencies
    engine.cache = AsyncMock()
    engine.cache.get = AsyncMock(return_value=None)
    engine.cache.set = AsyncMock()

    engine.metrics = MagicMock()
    engine.metrics.increment = MagicMock()

    engine.db_pool = AsyncMock()

    return engine


@pytest.fixture
def engine_no_spread():
    """
    ArbitrageEngine wired with two mock exchanges whose orderbooks
    have NO profitable spread (exchange_b bid < exchange_a ask).
    """
    config = _make_config()
    engine = ArbitrageEngine(config)

    ob_a = {
        "bids": [[67000, 2.0], [66900, 3.0]],
        "asks": [[67100, 2.0], [67200, 3.0]],
    }
    ob_b = {
        "bids": [[67050, 2.0], [66950, 3.0]],
        "asks": [[67150, 2.0], [67250, 3.0]],
    }

    engine.exchanges = {
        "exchange_a": _make_mock_exchange(ob_a),
        "exchange_b": _make_mock_exchange(ob_b),
    }

    engine.cache = AsyncMock()
    engine.cache.get = AsyncMock(return_value=None)
    engine.cache.set = AsyncMock()

    engine.metrics = MagicMock()
    engine.metrics.increment = MagicMock()

    engine.db_pool = AsyncMock()

    return engine


@pytest.mark.asyncio
async def test_find_arbitrage_detects_profitable_spread(engine_with_spread):
    """
    Given exchange_a ask=67000 and exchange_b bid=67300 (~0.45% gross spread),
    find_arbitrage should return an Opportunity buying on exchange_a and
    selling on exchange_b with positive estimated profit.
    """
    opp = await engine_with_spread.find_arbitrage("BTC/USDT")

    assert opp is not None, "Expected an Opportunity but got None"
    assert isinstance(opp, Opportunity)
    assert opp.buy_exchange == "exchange_a"
    assert opp.sell_exchange == "exchange_b"
    assert opp.buy_price == Decimal("67000")
    assert opp.sell_price == Decimal("67300")
    assert opp.estimated_profit_usd > 0
    assert opp.spread_percent > 0
    assert opp.symbol == "BTC/USDT"


@pytest.mark.asyncio
async def test_find_arbitrage_returns_none_when_no_spread(engine_no_spread):
    """
    When the best bid on every exchange is below the best ask on every
    other exchange (after fees and slippage), find_arbitrage should
    return None.
    """
    opp = await engine_no_spread.find_arbitrage("BTC/USDT")

    assert opp is None, f"Expected None but got opportunity with spread {opp.spread_percent}%"


@pytest.mark.asyncio
async def test_calculate_spread_fields_are_consistent(engine_with_spread):
    """
    Verify that the Opportunity returned by the pipeline has internally
    consistent field values (spread direction, fee fields populated, etc.).
    """
    opp = await engine_with_spread.find_arbitrage("BTC/USDT")

    assert opp is not None
    # sell_price must exceed buy_price for a profitable opportunity
    assert opp.sell_price > opp.buy_price
    # spread in bps should be 100x spread in percent
    expected_bps = opp.spread_percent * 100
    assert abs(opp.spread_bps - expected_bps) < Decimal("0.01")
    # fee fields should be populated (0.1% = taker_fee 0.001 * 100)
    assert opp.buy_fee_percent == Decimal("0.1")
    assert opp.sell_fee_percent == Decimal("0.1")
