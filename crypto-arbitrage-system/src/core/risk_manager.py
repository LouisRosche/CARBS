"""
Advanced Risk Management System

Implements quantitative risk management with:
- Kelly Criterion position sizing
- Value at Risk (VaR) at 95% and 99% confidence
- Expected Shortfall (CVaR)
- Sharpe and Sortino ratios
- Maximum drawdown tracking
- Dynamic position sizing
- Portfolio constraints

Research References:
- Kelly, J.L. (1956): A New Interpretation of Information Rate
- Jorion, P. (2007): Value at Risk: The New Benchmark
- Sortino & Price (1994): Performance Measurement in a Downside Risk Framework
"""

import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Deque, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from collections import deque
import logging

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Record of a completed trade"""
    timestamp: datetime
    symbol: str
    buy_exchange: str
    sell_exchange: str
    position_size: Decimal
    gross_profit: Decimal
    net_profit: Decimal
    fees: Decimal
    execution_time_ms: int
    success: bool


@dataclass
class PositionRisk:
    """Risk metrics for a position"""
    symbol: str
    position_size_usd: Decimal
    optimal_size_kelly: Decimal
    max_size_constraint: Decimal
    recommended_size: Decimal
    expected_return: Decimal
    expected_volatility: Decimal
    sharpe_ratio: float
    win_probability: float
    risk_score: float  # 0-1, higher = riskier


@dataclass
class PortfolioRisk:
    """Portfolio-level risk metrics"""
    total_positions_usd: Decimal
    var_95: Decimal  # Value at Risk 95% confidence
    var_99: Decimal  # Value at Risk 99% confidence
    expected_shortfall: Decimal  # CVaR
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: Decimal
    max_drawdown_percent: float
    current_drawdown: Decimal
    win_rate: float
    profit_factor: float  # Gross profit / Gross loss
    avg_win: Decimal
    avg_loss: Decimal
    total_trades: int


class KellyCriterion:
    """
    Kelly Criterion for optimal position sizing

    Based on: Kelly, J.L. (1956)
    "A New Interpretation of Information Rate"

    Formula: f* = (p * b - q) / b
    Where:
        f* = optimal fraction of capital
        p = probability of win
        b = ratio of win to loss (avg_win / avg_loss)
        q = probability of loss (1 - p)
    """

    @staticmethod
    def calculate_position_size(
        capital: Decimal,
        win_probability: float,
        avg_win: Decimal,
        avg_loss: Decimal,
        safety_factor: float = 0.25,
        max_fraction: float = 0.10
    ) -> Decimal:
        """
        Calculate optimal position size using Kelly Criterion

        Args:
            capital: Available capital
            win_probability: Probability of profitable trade (0-1)
            avg_win: Average winning trade amount
            avg_loss: Average losing trade amount (positive number)
            safety_factor: Reduce Kelly by this factor (0.25 = quarter Kelly)
            max_fraction: Maximum fraction of capital to risk (default 10%)

        Returns:
            Optimal position size in USD
        """
        if avg_loss == 0 or win_probability <= 0 or win_probability >= 1:
            return Decimal('0')

        # Convert all values to Decimal for precision
        p = Decimal(str(win_probability))
        q = Decimal('1') - p
        b = avg_win / avg_loss if avg_loss > 0 else Decimal('0')
        safety = Decimal(str(safety_factor))

        if b <= 0:
            return Decimal('0')

        # Kelly formula: f* = (p * b - q) / b
        kelly_fraction = (p * b - q) / b

        # Don't bet if Kelly is negative
        if kelly_fraction <= 0:
            return Decimal('0')

        # Apply safety factor (typically 0.25 for quarter-Kelly)
        safe_kelly = kelly_fraction * safety

        # Cap at configurable maximum fraction of capital
        max_fraction_decimal = Decimal(str(max_fraction))
        safe_kelly = min(safe_kelly, max_fraction_decimal)

        position_size = capital * safe_kelly

        return position_size

    @staticmethod
    def calculate_win_probability(
        trade_history: List[TradeRecord],
        lookback: int = 50
    ) -> float:
        """Calculate empirical win probability from recent trades"""
        if not trade_history:
            return 0.5  # Default 50% if no history

        recent = trade_history[-lookback:]
        wins = sum(1 for t in recent if t.net_profit > 0)
        total = len(recent)

        return wins / total if total > 0 else 0.5


class ValueAtRisk:
    """
    Value at Risk (VaR) and Expected Shortfall (CVaR) calculations

    Based on: Jorion, P. (2007)
    "Value at Risk: The New Benchmark for Managing Financial Risk"
    """

    @staticmethod
    def calculate_var(
        returns: List[float],
        confidence: float = 0.95
    ) -> float:
        """
        Calculate Value at Risk using historical simulation

        Args:
            returns: List of historical returns
            confidence: Confidence level (0.95 = 95%)

        Returns:
            VaR as a positive number (e.g., 0.05 = 5% loss)
        """
        if not returns or len(returns) < 10:
            return 0.0

        returns_array = np.array(returns)

        # Historical simulation method
        var = np.percentile(returns_array, (1 - confidence) * 100)

        # Return as positive number (loss)
        return abs(float(var))

    @staticmethod
    def calculate_expected_shortfall(
        returns: List[float],
        confidence: float = 0.95
    ) -> float:
        """
        Calculate Expected Shortfall (CVaR)

        Average loss beyond VaR threshold

        Args:
            returns: List of historical returns
            confidence: Confidence level (0.95 = 95%)

        Returns:
            Expected Shortfall as positive number
        """
        if not returns or len(returns) < 10:
            return 0.0

        returns_array = np.array(returns)

        # Find VaR threshold
        var_threshold = np.percentile(returns_array, (1 - confidence) * 100)

        # Calculate average of losses beyond VaR
        tail_losses = returns_array[returns_array <= var_threshold]

        if len(tail_losses) > 0:
            es = np.mean(tail_losses)
            return abs(float(es))

        return 0.0


class PerformanceMetrics:
    """
    Calculate performance metrics (Sharpe, Sortino, etc.)
    """

    @staticmethod
    def calculate_sharpe_ratio(
        returns: List[float],
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate Sharpe Ratio

        Args:
            returns: Period returns
            risk_free_rate: Annual risk-free rate
            periods_per_year: Number of periods per year (252 for daily)

        Returns:
            Annualized Sharpe ratio
        """
        if not returns or len(returns) < 2:
            return 0.0

        returns_array = np.array(returns)
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array, ddof=1)

        if std_return == 0:
            return 0.0

        # Annualized
        sharpe = (mean_return - risk_free_rate / periods_per_year) / std_return
        sharpe *= np.sqrt(periods_per_year)

        return float(sharpe)

    @staticmethod
    def calculate_sortino_ratio(
        returns: List[float],
        target_return: float = 0.0,
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate Sortino Ratio (downside deviation only)

        Args:
            returns: Period returns
            target_return: Target/minimum acceptable return
            periods_per_year: Number of periods per year

        Returns:
            Annualized Sortino ratio
        """
        if not returns or len(returns) < 2:
            return 0.0

        returns_array = np.array(returns)
        mean_return = np.mean(returns_array)

        # Downside deviation (only negative returns)
        downside_returns = returns_array[returns_array < target_return]
        if len(downside_returns) < 2:
            return 0.0

        downside_std = np.std(downside_returns, ddof=1)

        if downside_std == 0:
            return 0.0

        # Annualized
        sortino = (mean_return - target_return) / downside_std
        sortino *= np.sqrt(periods_per_year)

        return float(sortino)

    @staticmethod
    def calculate_max_drawdown(
        equity_curve: List[float]
    ) -> Tuple[float, float]:
        """
        Calculate maximum drawdown

        Args:
            equity_curve: List of portfolio values over time

        Returns:
            (max_drawdown_amount, max_drawdown_percent)
        """
        if not equity_curve or len(equity_curve) < 2:
            return 0.0, 0.0

        curve = np.array(equity_curve)
        running_max = np.maximum.accumulate(curve)
        drawdown = curve - running_max
        max_dd = np.min(drawdown)
        max_dd_pct = max_dd / np.max(running_max) if np.max(running_max) > 0 else 0.0

        return float(max_dd), float(max_dd_pct)


class RiskManager:
    """
    Advanced Risk Management System

    Features:
    - Kelly Criterion position sizing
    - VaR and Expected Shortfall
    - Sharpe and Sortino ratios
    - Maximum drawdown tracking
    - Dynamic position sizing
    - Portfolio constraints
    """

    def __init__(self, config):
        """
        Args:
            config: System configuration
        """
        self.config = config
        self.trade_history: Deque[TradeRecord] = deque(maxlen=1000)
        self.equity_curve: Deque[float] = deque(maxlen=10000)
        self.daily_pnl: Dict[str, Decimal] = {}  # date -> pnl

        # Risk parameters
        self.max_position_usd = Decimal(str(config.trading.max_position_usd))
        self.max_daily_loss = Decimal(str(config.trading.max_daily_loss_usd))
        self.max_portfolio_risk_pct = 0.10  # Max 10% of capital at risk

        # Kelly parameters from config (with backwards-compatible defaults)
        risk_cfg = getattr(config, 'risk_management', {}) or {}
        self.kelly_max_fraction = float(risk_cfg.get('kelly_max_fraction', 0.10))
        self.kelly_safety_factor = float(risk_cfg.get('kelly_safety_factor', 0.25))

        logger.info(
            f"Kelly parameters: max_fraction={self.kelly_max_fraction}, "
            f"safety_factor={self.kelly_safety_factor}"
        )

        # Performance tracking
        self.starting_capital = Decimal('10000')  # Default
        self.current_capital = self.starting_capital
        self.peak_capital = self.starting_capital

        logger.info("✨ Risk Manager initialized")

    def record_trade(self, trade: TradeRecord):
        """Record a completed trade"""
        self.trade_history.append(trade)

        # Update capital
        self.current_capital += trade.net_profit

        # Update equity curve
        self.equity_curve.append(float(self.current_capital))

        # Update peak
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital

        # Update daily P&L
        date_key = trade.timestamp.date().isoformat()
        if date_key not in self.daily_pnl:
            self.daily_pnl[date_key] = Decimal('0')
        self.daily_pnl[date_key] += trade.net_profit

        logger.debug(f"Trade recorded: {trade.net_profit:.2f} USD")

    def calculate_position_risk(
        self,
        symbol: str,
        expected_spread: Decimal,
        expected_fees: Decimal,
        volatility: float
    ) -> PositionRisk:
        """
        Calculate risk metrics for a potential position

        Returns:
            PositionRisk with recommended position size
        """
        # Calculate statistics from history
        if len(self.trade_history) >= 10:
            wins = [t for t in self.trade_history if t.net_profit > 0]
            losses = [t for t in self.trade_history if t.net_profit < 0]

            total_trades = len(self.trade_history)
            win_prob = len(wins) / total_trades if total_trades > 0 else 0.5
            avg_win = sum(t.net_profit for t in wins) / len(wins) if wins else Decimal('0')
            avg_loss = abs(sum(t.net_profit for t in losses) / len(losses)) if losses else Decimal('1')
        else:
            # Bootstrap with conservative estimates
            win_prob = 0.55
            avg_win = expected_spread * Decimal('0.8')  # Conservative
            avg_loss = expected_fees * Decimal('2')  # Pessimistic

        # Kelly Criterion optimal size
        kelly_size = KellyCriterion.calculate_position_size(
            capital=self.current_capital,
            win_probability=win_prob,
            avg_win=avg_win,
            avg_loss=avg_loss,
            safety_factor=self.kelly_safety_factor,
            max_fraction=self.kelly_max_fraction
        )

        # Apply constraints
        max_size = min(
            self.max_position_usd,
            self.current_capital * Decimal('0.10')  # Max 10% of capital
        )

        recommended_size = min(kelly_size, max_size)

        # Calculate expected return and risk
        expected_return = expected_spread - expected_fees
        expected_volatility = Decimal(str(volatility))

        # Risk score (0-1, higher = riskier)
        risk_score = self._calculate_risk_score(
            position_size=recommended_size,
            volatility=volatility,
            win_prob=win_prob
        )

        # Sharpe approximation
        if volatility > 0:
            sharpe = float(expected_return / expected_volatility)
        else:
            sharpe = 0.0

        return PositionRisk(
            symbol=symbol,
            position_size_usd=recommended_size,
            optimal_size_kelly=kelly_size,
            max_size_constraint=max_size,
            recommended_size=recommended_size,
            expected_return=expected_return,
            expected_volatility=expected_volatility,
            sharpe_ratio=sharpe,
            win_probability=win_prob,
            risk_score=risk_score
        )

    def _calculate_risk_score(
        self,
        position_size: Decimal,
        volatility: float,
        win_prob: float
    ) -> float:
        """
        Calculate composite risk score (0-1)

        Higher = riskier
        """
        # Size risk (larger positions = higher risk)
        size_ratio = float(position_size / self.current_capital) if self.current_capital > 0 else 0
        size_risk = min(size_ratio * 10, 1.0)  # Cap at 1.0

        # Volatility risk
        vol_risk = min(volatility / 2.0, 1.0)  # Normalize, cap at 1.0

        # Win probability risk (lower win rate = higher risk)
        prob_risk = 1.0 - win_prob

        # Weighted average
        risk_score = (
            size_risk * 0.3 +
            vol_risk * 0.5 +
            prob_risk * 0.2
        )

        return risk_score

    def calculate_portfolio_risk(self) -> PortfolioRisk:
        """
        Calculate portfolio-level risk metrics

        Returns:
            PortfolioRisk with VaR, Sharpe, drawdown, etc.
        """
        if len(self.trade_history) < 10:
            # Not enough data, return defaults
            return PortfolioRisk(
                total_positions_usd=Decimal('0'),
                var_95=Decimal('0'),
                var_99=Decimal('0'),
                expected_shortfall=Decimal('0'),
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                max_drawdown=Decimal('0'),
                max_drawdown_percent=0.0,
                current_drawdown=Decimal('0'),
                win_rate=0.5,
                profit_factor=0.0,
                avg_win=Decimal('0'),
                avg_loss=Decimal('0'),
                total_trades=0
            )

        # Calculate returns
        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_value = self.equity_curve[i-1]
            if prev_value != 0:
                ret = (self.equity_curve[i] - prev_value) / prev_value
                returns.append(ret)

        # VaR calculations
        var_95 = ValueAtRisk.calculate_var(returns, confidence=0.95)
        var_99 = ValueAtRisk.calculate_var(returns, confidence=0.99)
        expected_shortfall = ValueAtRisk.calculate_expected_shortfall(returns, confidence=0.95)

        # Convert to dollar amounts
        var_95_usd = Decimal(str(var_95)) * self.current_capital
        var_99_usd = Decimal(str(var_99)) * self.current_capital
        es_usd = Decimal(str(expected_shortfall)) * self.current_capital

        # Sharpe and Sortino
        sharpe = PerformanceMetrics.calculate_sharpe_ratio(returns, periods_per_year=43200)  # ~1 trade per 2 sec
        sortino = PerformanceMetrics.calculate_sortino_ratio(returns, periods_per_year=43200)

        # Maximum drawdown
        max_dd, max_dd_pct = PerformanceMetrics.calculate_max_drawdown(list(self.equity_curve))
        current_dd = float(self.peak_capital - self.current_capital)

        # Win statistics
        wins = [t for t in self.trade_history if t.net_profit > 0]
        losses = [t for t in self.trade_history if t.net_profit < 0]

        total_trades = len(self.trade_history)
        win_rate = len(wins) / total_trades if total_trades > 0 else 0.5
        avg_win = sum(t.net_profit for t in wins) / len(wins) if wins else Decimal('0')
        avg_loss = abs(sum(t.net_profit for t in losses) / len(losses)) if losses else Decimal('0')

        total_wins = sum(t.net_profit for t in wins)
        total_losses = abs(sum(t.net_profit for t in losses))
        profit_factor = float(total_wins / total_losses) if total_losses > 0 else 0.0

        return PortfolioRisk(
            total_positions_usd=self.current_capital,
            var_95=var_95_usd,
            var_99=var_99_usd,
            expected_shortfall=es_usd,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=Decimal(str(max_dd)),
            max_drawdown_percent=max_dd_pct,
            current_drawdown=Decimal(str(current_dd)),
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            total_trades=len(self.trade_history)
        )

    def check_risk_limits(self) -> Tuple[bool, Optional[str]]:
        """
        Check if current risk is within limits

        Returns:
            (is_allowed, reason_if_not)
        """
        # Check daily loss limit
        today = datetime.now(timezone.utc).date().isoformat()
        daily_loss = abs(self.daily_pnl.get(today, Decimal('0')))

        if daily_loss >= self.max_daily_loss:
            return False, f"Daily loss limit reached: ${daily_loss:.2f}"

        # Check drawdown
        current_dd = self.peak_capital - self.current_capital
        dd_percent = float(current_dd / self.peak_capital) if self.peak_capital > 0 else 0

        if dd_percent > 0.20:  # 20% max drawdown
            return False, f"Maximum drawdown exceeded: {dd_percent:.1%}"

        # Check if we have enough capital
        if self.current_capital < self.starting_capital * Decimal('0.5'):
            return False, "Capital below 50% of starting amount"

        return True, None

    def should_reduce_risk(self) -> bool:
        """Check if we should reduce position sizes due to recent performance"""
        if len(self.trade_history) < 20:
            return False

        # Check recent win rate
        recent = list(self.trade_history)[-20:]
        recent_wins = sum(1 for t in recent if t.net_profit > 0)
        recent_win_rate = recent_wins / len(recent)

        # Reduce risk if win rate drops below 40%
        if recent_win_rate < 0.40:
            logger.warning(f"Reducing risk due to low win rate: {recent_win_rate:.1%}")
            return True

        # Check current drawdown
        current_dd_pct = float((self.peak_capital - self.current_capital) / self.peak_capital) if self.peak_capital > 0 else 0.0
        if current_dd_pct > 0.10:  # 10% drawdown
            logger.warning(f"Reducing risk due to drawdown: {current_dd_pct:.1%}")
            return True

        return False

    def get_risk_summary(self) -> Dict:
        """Get human-readable risk summary"""
        portfolio_risk = self.calculate_portfolio_risk()

        return {
            'current_capital': float(self.current_capital),
            'peak_capital': float(self.peak_capital),
            'total_trades': portfolio_risk.total_trades,
            'win_rate': f"{portfolio_risk.win_rate:.1%}",
            'sharpe_ratio': f"{portfolio_risk.sharpe_ratio:.2f}",
            'sortino_ratio': f"{portfolio_risk.sortino_ratio:.2f}",
            'max_drawdown': f"{portfolio_risk.max_drawdown_percent:.1%}",
            'var_95': f"${portfolio_risk.var_95:.2f}",
            'var_99': f"${portfolio_risk.var_99:.2f}",
            'profit_factor': f"{portfolio_risk.profit_factor:.2f}",
            'avg_win': f"${portfolio_risk.avg_win:.2f}",
            'avg_loss': f"${portfolio_risk.avg_loss:.2f}"
        }
