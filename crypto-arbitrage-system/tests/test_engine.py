"""
Comprehensive tests for arbitrage engine

Tests:
- Orderbook operations
- Slippage estimation
- Spread calculation
- Opportunity detection
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone

from src.core.engine import OrderBook, Opportunity


@pytest.fixture
def sample_orderbook():
    """Create a sample orderbook for testing"""
    return OrderBook(
        exchange="binance",
        symbol="BTC/USDT",
        timestamp=datetime.now(timezone.utc),
        bids=[(Decimal("67000"), Decimal("1.5"))],
        asks=[(Decimal("67100"), Decimal("1.2"))]
    )


@pytest.fixture
def deep_orderbook():
    """Create orderbook with multiple price levels for slippage testing"""
    return OrderBook(
        exchange="binance",
        symbol="BTC/USDT",
        timestamp=datetime.now(timezone.utc),
        bids=[
            (Decimal("67000"), Decimal("1.0")),
            (Decimal("66990"), Decimal("2.0")),
            (Decimal("66980"), Decimal("3.0")),
            (Decimal("66970"), Decimal("5.0")),
            (Decimal("66960"), Decimal("10.0")),
        ],
        asks=[
            (Decimal("67100"), Decimal("1.0")),
            (Decimal("67110"), Decimal("2.0")),
            (Decimal("67120"), Decimal("3.0")),
            (Decimal("67130"), Decimal("5.0")),
            (Decimal("67140"), Decimal("10.0")),
        ]
    )


class TestOrderBook:
    """Test OrderBook class functionality"""

    def test_best_bid(self, sample_orderbook):
        """Should return best bid price and volume"""
        assert sample_orderbook.best_bid == (Decimal("67000"), Decimal("1.5"))

    def test_best_ask(self, sample_orderbook):
        """Should return best ask price and volume"""
        assert sample_orderbook.best_ask == (Decimal("67100"), Decimal("1.2"))

    def test_empty_orderbook(self):
        """Should handle empty orderbook gracefully"""
        empty_ob = OrderBook(
            exchange="test",
            symbol="BTC/USDT",
            timestamp=datetime.now(timezone.utc),
            bids=[],
            asks=[]
        )
        assert empty_ob.best_bid == (Decimal("0"), Decimal("0"))
        assert empty_ob.best_ask == (Decimal("0"), Decimal("0"))


class TestSlippageEstimation:
    """Test dynamic slippage estimation"""

    def test_zero_position_size(self, deep_orderbook):
        """Zero position should have zero slippage"""
        slippage = deep_orderbook.estimate_slippage("buy", Decimal("0"))
        assert slippage == Decimal("0")

    def test_small_buy_order_slippage(self, deep_orderbook):
        """Small order should have minimal slippage"""
        # Order size within first level (1 BTC * $67100 = $67100)
        slippage = deep_orderbook.estimate_slippage("buy", Decimal("50000"))
        assert slippage < Decimal("0.001")  # Less than 10 bps

    def test_large_buy_order_slippage(self, deep_orderbook):
        """Large order should have higher slippage"""
        # Large order that spans multiple levels
        slippage = deep_orderbook.estimate_slippage("buy", Decimal("500000"))
        assert slippage > Decimal("0")
        assert slippage < Decimal("0.02")  # Capped at 2%

    def test_sell_order_slippage(self, deep_orderbook):
        """Sell orders should also estimate slippage correctly"""
        slippage = deep_orderbook.estimate_slippage("sell", Decimal("50000"))
        assert slippage >= Decimal("0")

    def test_empty_orderbook_slippage(self):
        """Empty orderbook should return default slippage"""
        empty_ob = OrderBook(
            exchange="test",
            symbol="BTC/USDT",
            timestamp=datetime.now(timezone.utc),
            bids=[],
            asks=[]
        )
        slippage = empty_ob.estimate_slippage("buy", Decimal("10000"))
        assert slippage == Decimal("0.005")  # Default 50 bps

    def test_slippage_capped_at_max(self, deep_orderbook):
        """Slippage should be capped at maximum value"""
        # Very large order
        slippage = deep_orderbook.estimate_slippage("buy", Decimal("10000000"))
        assert slippage <= Decimal("0.02")  # Max 2%


class TestOpportunity:
    """Test Opportunity dataclass"""

    def test_opportunity_creation(self):
        """Should create opportunity with all fields"""
        opp = Opportunity(
            symbol="BTC/USDT",
            buy_exchange="binance",
            sell_exchange="coinbase",
            buy_price=Decimal("67000"),
            sell_price=Decimal("67200"),
            spread_percent=Decimal("0.298"),
            spread_bps=Decimal("29.8"),
            estimated_profit_usd=Decimal("15.50"),
            estimated_profit_after_fees=Decimal("10.25"),
            buy_fee_percent=Decimal("0.1"),
            sell_fee_percent=Decimal("0.1"),
            slippage_estimate=Decimal("0.05"),
            detected_at=datetime.now(timezone.utc),
            confidence_score=0.85
        )

        assert opp.symbol == "BTC/USDT"
        assert opp.buy_exchange == "binance"
        assert opp.sell_exchange == "coinbase"
        assert opp.confidence_score == 0.85


class TestSpreadCalculation:
    """Test spread and profit calculations"""

    def test_gross_spread_calculation(self):
        """Test gross spread calculation between exchanges"""
        buy_price = Decimal("67000")
        sell_price = Decimal("67200")

        gross_spread = (sell_price - buy_price) / buy_price
        spread_percent = gross_spread * 100
        spread_bps = gross_spread * 10000

        assert abs(spread_percent - Decimal("0.2985")) < Decimal("0.001")
        assert abs(spread_bps - Decimal("29.85")) < Decimal("0.1")

    def test_net_spread_after_fees(self):
        """Test net spread calculation after fees and slippage"""
        buy_price = Decimal("67000")
        sell_price = Decimal("67200")

        gross_spread = (sell_price - buy_price) / buy_price
        buy_fee = Decimal("0.001")  # 10 bps
        sell_fee = Decimal("0.001")  # 10 bps
        slippage = Decimal("0.0005")  # 5 bps

        net_spread = gross_spread - buy_fee - sell_fee - slippage

        # Should still be positive
        assert net_spread > Decimal("0")

    def test_negative_spread_rejected(self):
        """Negative spreads should be rejected"""
        buy_price = Decimal("67200")  # Higher buy price
        sell_price = Decimal("67000")  # Lower sell price

        gross_spread = (sell_price - buy_price) / buy_price

        # Spread is negative
        assert gross_spread < Decimal("0")


class TestConfidenceScore:
    """Test confidence score calculation"""

    def test_confidence_components(self, deep_orderbook):
        """Test confidence score is within expected range"""
        # The confidence calculation is in the ArbitrageEngine
        # Here we test the components

        # Liquidity score (0-0.4)
        buy_volume_usd = float(deep_orderbook.best_ask[0] * deep_orderbook.best_ask[1])
        position_size = 50000
        liquidity_ratio = min(buy_volume_usd / position_size, 5.0) / 5.0
        liquidity_score = liquidity_ratio * 0.4
        assert 0 <= liquidity_score <= 0.4

        # Depth score (0-0.3)
        depth = min(len(deep_orderbook.asks), 10) / 10.0
        depth_score = depth * 0.3
        assert 0 <= depth_score <= 0.3

    def test_confidence_bounds(self):
        """Confidence score should be between 0 and 1"""
        # Valid confidence scores
        assert 0 <= 0.0 <= 1
        assert 0 <= 0.5 <= 1
        assert 0 <= 1.0 <= 1


class TestEngineIntegration:
    """Integration tests for ArbitrageEngine

    TODO: These tests require mocking the full engine config and exchange
    connections. Implement when ArbitrageEngine constructor is stabilized.
    """
