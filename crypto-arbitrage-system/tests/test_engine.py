"""Tests for arbitrage engine"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone

from core.engine import OrderBook, ArbitrageEngine


@pytest.fixture
def sample_orderbook():
    return OrderBook(
        exchange="binance",
        symbol="BTC/USDT",
        timestamp=datetime.now(timezone.utc),
        bids=[(Decimal("67000"), Decimal("1.5"))],
        asks=[(Decimal("67100"), Decimal("1.2"))]
    )


def test_orderbook_best_prices(sample_orderbook):
    assert sample_orderbook.best_bid == (Decimal("67000"), Decimal("1.5"))
    assert sample_orderbook.best_ask == (Decimal("67100"), Decimal("1.2"))


@pytest.mark.asyncio
async def test_engine_initialization():
    """Test engine can be initialized"""
    # This would require mocking config
    pass
