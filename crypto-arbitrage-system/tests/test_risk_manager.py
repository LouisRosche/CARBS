"""
Comprehensive tests for risk manager module

Tests:
- Kelly Criterion position sizing
- Decimal precision handling
- Edge cases and boundary conditions
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from dataclasses import dataclass


@dataclass
class MockTradeRecord:
    """Mock trade record for testing"""
    trade_id: str
    pnl: Decimal
    timestamp: datetime


class TestKellyCriterion:
    """Test Kelly Criterion position sizing"""

    def test_position_size_basic(self):
        """Test basic position size calculation"""
        from core.risk_manager import KellyCriterion

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
        from core.risk_manager import KellyCriterion

        size = KellyCriterion.calculate_position_size(
            capital=Decimal('10000'),
            win_probability=0.6,
            avg_win=Decimal('100'),
            avg_loss=Decimal('0')
        )

        assert size == Decimal('0')

    def test_position_size_edge_probability(self):
        """Should return 0 for edge probability values"""
        from core.risk_manager import KellyCriterion

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
        from core.risk_manager import KellyCriterion

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
        from core.risk_manager import KellyCriterion

        base_size = KellyCriterion.calculate_position_size(
            capital=Decimal('10000'),
            win_probability=0.6,
            avg_win=Decimal('100'),
            avg_loss=Decimal('50'),
            safety_factor=1.0
        )

        quarter_kelly = KellyCriterion.calculate_position_size(
            capital=Decimal('10000'),
            win_probability=0.6,
            avg_win=Decimal('100'),
            avg_loss=Decimal('50'),
            safety_factor=0.25
        )

        # Quarter Kelly should be smaller
        assert quarter_kelly < base_size

    def test_position_size_decimal_precision(self):
        """Should maintain decimal precision throughout calculation"""
        from core.risk_manager import KellyCriterion

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
        from core.risk_manager import KellyCriterion

        trades = [
            MockTradeRecord("1", Decimal('100'), datetime.now(timezone.utc)),
            MockTradeRecord("2", Decimal('-50'), datetime.now(timezone.utc)),
            MockTradeRecord("3", Decimal('75'), datetime.now(timezone.utc)),
            MockTradeRecord("4", Decimal('25'), datetime.now(timezone.utc)),
        ]

        prob = KellyCriterion.calculate_win_probability(trades)

        # 3 wins out of 4 trades
        assert prob == 0.75

    def test_calculate_win_probability_no_trades(self):
        """Should return 0.5 for empty trade history"""
        from core.risk_manager import KellyCriterion

        prob = KellyCriterion.calculate_win_probability([])
        assert prob == 0.5

    def test_calculate_avg_win_loss(self):
        """Test average win/loss calculation"""
        from core.risk_manager import KellyCriterion

        trades = [
            MockTradeRecord("1", Decimal('100'), datetime.now(timezone.utc)),
            MockTradeRecord("2", Decimal('-50'), datetime.now(timezone.utc)),
            MockTradeRecord("3", Decimal('200'), datetime.now(timezone.utc)),
            MockTradeRecord("4", Decimal('-100'), datetime.now(timezone.utc)),
        ]

        avg_win, avg_loss = KellyCriterion.calculate_avg_win_loss(trades)

        assert avg_win == Decimal('150')  # (100 + 200) / 2
        assert avg_loss == Decimal('75')  # (50 + 100) / 2


class TestRiskMetrics:
    """Test risk metric calculations"""

    def test_var_calculation(self):
        """Test Value at Risk calculation"""
        from core.risk_manager import RiskMetrics

        returns = [
            Decimal('-0.02'),
            Decimal('0.01'),
            Decimal('-0.03'),
            Decimal('0.02'),
            Decimal('-0.01'),
            Decimal('0.015'),
            Decimal('-0.025'),
            Decimal('0.005'),
            Decimal('-0.015'),
            Decimal('0.01'),
        ]

        var_95 = RiskMetrics.calculate_var(returns, confidence=0.95)

        # VaR should be positive (representing loss)
        assert var_95 >= Decimal('0')

    def test_max_drawdown(self):
        """Test maximum drawdown calculation"""
        from core.risk_manager import RiskMetrics

        equity_curve = [
            Decimal('10000'),
            Decimal('10500'),
            Decimal('10200'),  # Drawdown starts
            Decimal('9800'),   # Deeper drawdown
            Decimal('10100'),  # Recovery
            Decimal('10600'),  # New high
        ]

        max_dd = RiskMetrics.calculate_max_drawdown(equity_curve)

        # Max drawdown should be from 10500 to 9800
        expected_dd = (Decimal('10500') - Decimal('9800')) / Decimal('10500')
        assert abs(max_dd - expected_dd) < Decimal('0.001')

    def test_sharpe_ratio(self):
        """Test Sharpe ratio calculation"""
        from core.risk_manager import RiskMetrics

        returns = [
            Decimal('0.01'),
            Decimal('0.02'),
            Decimal('-0.005'),
            Decimal('0.015'),
            Decimal('0.008'),
        ]

        sharpe = RiskMetrics.calculate_sharpe_ratio(
            returns,
            risk_free_rate=Decimal('0.001')
        )

        # Sharpe should be positive for positive returns
        assert sharpe > 0

    def test_sortino_ratio(self):
        """Test Sortino ratio calculation"""
        from core.risk_manager import RiskMetrics

        returns = [
            Decimal('0.01'),
            Decimal('0.02'),
            Decimal('-0.005'),
            Decimal('0.015'),
            Decimal('-0.008'),
        ]

        sortino = RiskMetrics.calculate_sortino_ratio(
            returns,
            risk_free_rate=Decimal('0.001')
        )

        # Sortino should be defined
        assert sortino is not None


class TestRiskManager:
    """Test RiskManager class"""

    def test_check_daily_loss_limit(self):
        """Test daily loss limit checking"""
        from core.risk_manager import RiskManager

        manager = RiskManager(
            daily_loss_limit=Decimal('100'),
            max_position_percent=Decimal('10')
        )

        # Record some losses
        manager.record_trade_result(Decimal('-30'))
        manager.record_trade_result(Decimal('-40'))

        # Should still be within limit
        assert manager.can_trade() is True

        # Record more losses to exceed limit
        manager.record_trade_result(Decimal('-50'))

        # Should now be blocked
        assert manager.can_trade() is False

    def test_position_limit_check(self):
        """Test position size limit"""
        from core.risk_manager import RiskManager

        manager = RiskManager(
            daily_loss_limit=Decimal('1000'),
            max_position_percent=Decimal('10')
        )

        capital = Decimal('10000')
        max_position = manager.get_max_position_size(capital)

        assert max_position == Decimal('1000')  # 10% of 10000

    def test_risk_reset_on_new_day(self):
        """Daily limits should reset on new day"""
        from core.risk_manager import RiskManager

        manager = RiskManager(
            daily_loss_limit=Decimal('100'),
            max_position_percent=Decimal('10')
        )

        # Record losses
        manager.record_trade_result(Decimal('-150'))
        assert manager.can_trade() is False

        # Reset for new day
        manager.reset_daily_limits()

        assert manager.can_trade() is True
