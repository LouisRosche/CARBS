"""
Comprehensive tests for risk manager module

Tests:
- Kelly Criterion position sizing
- Value at Risk / Expected Shortfall
- Performance metrics (Sharpe, Sortino, max drawdown)
- RiskManager daily loss / drawdown limits
- Decimal precision handling
- Edge cases and boundary conditions
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from unittest.mock import MagicMock


@dataclass
class MockConfig:
    """Minimal config stub accepted by RiskManager.__init__"""
    trading: MagicMock = None
    risk_management: dict = None

    def __post_init__(self):
        if self.trading is None:
            self.trading = MagicMock()
            self.trading.max_position_usd = 1000
            self.trading.max_daily_loss_usd = 100
        if self.risk_management is None:
            self.risk_management = {
                'kelly_max_fraction': 0.10,
                'kelly_safety_factor': 0.25,
            }


def _make_trade(net_profit, symbol='BTC/USDT'):
    """Build a TradeRecord accepted by RiskManager.record_trade."""
    from src.core.risk_manager import TradeRecord
    return TradeRecord(
        timestamp=datetime.now(timezone.utc),
        symbol=symbol,
        buy_exchange='binance',
        sell_exchange='mexc',
        position_size=Decimal('500'),
        gross_profit=net_profit,
        net_profit=net_profit,
        fees=Decimal('0'),
        execution_time_ms=100,
        success=net_profit > 0,
    )


class TestKellyCriterion:
    """Test Kelly Criterion position sizing"""

    def test_position_size_basic(self):
        """Test basic position size calculation"""
        from src.core.risk_manager import KellyCriterion

        capital = Decimal('10000')
        win_probability = 0.6
        avg_win = Decimal('100')
        avg_loss = Decimal('50')

        size = KellyCriterion.calculate_position_size(
            capital, win_probability, avg_win, avg_loss
        )

        assert size > Decimal('0')
        assert size <= capital * Decimal('0.10')  # Max 10%

    def test_position_size_zero_loss(self):
        """Should return 0 if avg_loss is 0"""
        from src.core.risk_manager import KellyCriterion

        size = KellyCriterion.calculate_position_size(
            capital=Decimal('10000'),
            win_probability=0.6,
            avg_win=Decimal('100'),
            avg_loss=Decimal('0')
        )

        assert size == Decimal('0')

    def test_position_size_edge_probability(self):
        """Should return 0 for edge probability values"""
        from src.core.risk_manager import KellyCriterion

        # Probability of 0
        size1 = KellyCriterion.calculate_position_size(
            capital=Decimal('10000'),
            win_probability=0.0,
            avg_win=Decimal('100'),
            avg_loss=Decimal('50')
        )
        assert size1 == Decimal('0')

        # Probability of 1
        size2 = KellyCriterion.calculate_position_size(
            capital=Decimal('10000'),
            win_probability=1.0,
            avg_win=Decimal('100'),
            avg_loss=Decimal('50')
        )
        assert size2 == Decimal('0')

    def test_position_size_negative_expectation(self):
        """Should return 0 for negative expected value"""
        from src.core.risk_manager import KellyCriterion

        # Low win rate with small wins vs large losses
        size = KellyCriterion.calculate_position_size(
            capital=Decimal('10000'),
            win_probability=0.3,
            avg_win=Decimal('50'),
            avg_loss=Decimal('100')
        )

        assert size == Decimal('0')

    def test_position_size_safety_factor(self):
        """Safety factor should reduce position size"""
        from src.core.risk_manager import KellyCriterion

        # Use max_fraction=0.50 so the cap doesn't mask the safety_factor difference
        base_size = KellyCriterion.calculate_position_size(
            capital=Decimal('10000'),
            win_probability=0.6,
            avg_win=Decimal('100'),
            avg_loss=Decimal('50'),
            safety_factor=1.0,
            max_fraction=0.50
        )

        quarter_kelly = KellyCriterion.calculate_position_size(
            capital=Decimal('10000'),
            win_probability=0.6,
            avg_win=Decimal('100'),
            avg_loss=Decimal('50'),
            safety_factor=0.25,
            max_fraction=0.50
        )

        # Quarter Kelly should be smaller
        assert quarter_kelly < base_size

    def test_position_size_decimal_precision(self):
        """Should maintain decimal precision throughout calculation"""
        from src.core.risk_manager import KellyCriterion

        size = KellyCriterion.calculate_position_size(
            capital=Decimal('10000.123456'),
            win_probability=0.55,
            avg_win=Decimal('100.5'),
            avg_loss=Decimal('50.25')
        )

        # Should return Decimal type
        assert isinstance(size, Decimal)

    def test_calculate_win_probability(self):
        """Test win probability calculation from trade history"""
        from src.core.risk_manager import KellyCriterion

        trades = [
            _make_trade(Decimal('100')),
            _make_trade(Decimal('-50')),
            _make_trade(Decimal('75')),
            _make_trade(Decimal('25')),
        ]

        prob = KellyCriterion.calculate_win_probability(trades)

        # 3 wins out of 4 trades
        assert prob == 0.75

    def test_calculate_win_probability_no_trades(self):
        """Should return 0.5 for empty trade history"""
        from src.core.risk_manager import KellyCriterion

        prob = KellyCriterion.calculate_win_probability([])
        assert prob == 0.5


class TestValueAtRisk:
    """Test Value at Risk calculations"""

    def test_var_calculation(self):
        """Test Value at Risk calculation"""
        from src.core.risk_manager import ValueAtRisk

        returns = [-0.02, 0.01, -0.03, 0.02, -0.01, 0.015, -0.025, 0.005, -0.015, 0.01]

        var_95 = ValueAtRisk.calculate_var(returns, confidence=0.95)

        # VaR should be positive (representing loss)
        assert var_95 >= 0

    def test_var_insufficient_data(self):
        """VaR should return 0 when data is insufficient"""
        from src.core.risk_manager import ValueAtRisk

        var_95 = ValueAtRisk.calculate_var([0.01, -0.01], confidence=0.95)
        assert var_95 == 0.0

    def test_expected_shortfall(self):
        """CVaR should be >= VaR"""
        from src.core.risk_manager import ValueAtRisk

        returns = [-0.02, 0.01, -0.03, 0.02, -0.01, 0.015, -0.025, 0.005, -0.015, 0.01]

        var = ValueAtRisk.calculate_var(returns, confidence=0.95)
        es = ValueAtRisk.calculate_expected_shortfall(returns, confidence=0.95)

        assert es >= var


class TestPerformanceMetrics:
    """Test Sharpe, Sortino, max drawdown"""

    def test_max_drawdown(self):
        """Test maximum drawdown calculation"""
        from src.core.risk_manager import PerformanceMetrics

        equity_curve = [10000.0, 10500.0, 10200.0, 9800.0, 10100.0, 10600.0]

        max_dd_amount, max_dd_pct = PerformanceMetrics.calculate_max_drawdown(equity_curve)

        # Max drawdown should be from 10500 to 9800 = -700
        assert max_dd_amount == pytest.approx(-700.0, abs=1.0)
        expected_pct = -700 / 10500
        assert max_dd_pct == pytest.approx(expected_pct, abs=0.001)

    def test_sharpe_ratio(self):
        """Test Sharpe ratio calculation"""
        from src.core.risk_manager import PerformanceMetrics

        returns = [0.01, 0.02, -0.005, 0.015, 0.008]

        sharpe = PerformanceMetrics.calculate_sharpe_ratio(returns, risk_free_rate=0.001)

        # Sharpe should be positive for net-positive returns
        assert sharpe > 0

    def test_sortino_ratio(self):
        """Test Sortino ratio calculation"""
        from src.core.risk_manager import PerformanceMetrics

        returns = [0.01, 0.02, -0.005, 0.015, -0.008]

        sortino = PerformanceMetrics.calculate_sortino_ratio(returns, target_return=0.0)

        # Sortino should be defined
        assert sortino is not None


class TestRiskManager:
    """Test RiskManager class using the real config-based constructor"""

    def test_check_daily_loss_limit(self):
        """Test daily loss limit checking"""
        from src.core.risk_manager import RiskManager

        cfg = MockConfig()
        cfg.trading.max_daily_loss_usd = 100
        manager = RiskManager(cfg)

        # Record some losses
        manager.record_trade(_make_trade(Decimal('-30')))
        manager.record_trade(_make_trade(Decimal('-40')))

        # Should still be within limit (70 < 100)
        allowed, _ = manager.check_risk_limits()
        assert allowed is True

        # Record more losses to exceed limit
        manager.record_trade(_make_trade(Decimal('-50')))

        # Should now be blocked (120 > 100)
        allowed, reason = manager.check_risk_limits()
        assert allowed is False
        assert "loss" in reason.lower() or "limit" in reason.lower()

    def test_position_limit_check(self):
        """max_position_usd should be stored correctly from config"""
        from src.core.risk_manager import RiskManager

        cfg = MockConfig()
        cfg.trading.max_position_usd = 1000
        manager = RiskManager(cfg)

        assert manager.max_position_usd == Decimal('1000')

    def test_risk_reset_on_new_day(self):
        """Daily limits track by date, so a new day starts fresh"""
        from src.core.risk_manager import RiskManager

        cfg = MockConfig()
        cfg.trading.max_daily_loss_usd = 100
        manager = RiskManager(cfg)

        # Record loss that exceeds limit
        manager.record_trade(_make_trade(Decimal('-150')))
        allowed, _ = manager.check_risk_limits()
        assert allowed is False

        # Simulate new day: clear today's P&L key
        manager.daily_pnl.clear()
        allowed, _ = manager.check_risk_limits()
        assert allowed is True
