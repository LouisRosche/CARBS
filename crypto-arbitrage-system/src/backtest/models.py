"""
Backtest Models

Dataclasses for OHLCV data, trades, and results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Tuple

from .enums import TimeFrame


@dataclass
class OHLCV:
    """Single candlestick"""
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "volume": str(self.volume)
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "OHLCV":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            open=Decimal(data["open"]),
            high=Decimal(data["high"]),
            low=Decimal(data["low"]),
            close=Decimal(data["close"]),
            volume=Decimal(data["volume"])
        )


@dataclass
class BacktestTrade:
    """Single trade in backtest"""
    trade_id: str
    entry_time: datetime
    exit_time: datetime = None
    asset: str = ""
    side: str = "long"  # long/short

    entry_price: Decimal = Decimal("0")
    exit_price: Decimal = None
    position_size: Decimal = Decimal("0")

    stop_loss: Decimal = None
    take_profit: Decimal = None

    # Costs
    entry_fee: Decimal = Decimal("0")
    exit_fee: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")

    # Results
    pnl: Decimal = None
    pnl_percent: Decimal = None
    status: str = "open"  # open, closed, stopped_out, take_profit

    # Signal info
    signal_confidence: float = 0.0
    signal_reasons: List[str] = field(default_factory=list)


@dataclass
class BacktestResult:
    """Complete backtest results"""
    backtest_id: str
    strategy_name: str
    asset: str
    timeframe: TimeFrame
    start_date: datetime
    end_date: datetime

    # Capital
    initial_capital: Decimal
    final_capital: Decimal
    peak_capital: Decimal = Decimal("0")
    trough_capital: Decimal = Decimal("0")

    # Trade stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    # Returns
    total_return: float = 0.0
    annualized_return: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration_days: int = 0

    # Risk metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Trade quality
    avg_win: Decimal = Decimal("0")
    avg_loss: Decimal = Decimal("0")
    profit_factor: float = 0.0
    expectancy: Decimal = Decimal("0")

    # Anti-fragility metrics
    tail_ratio: float = 0.0  # Positive outliers vs negative
    recovery_factor: float = 0.0  # Total profit / max drawdown
    ulcer_index: float = 0.0  # Depth and duration of drawdowns

    # Execution stats
    total_fees: Decimal = Decimal("0")
    total_slippage: Decimal = Decimal("0")
    avg_holding_period_hours: float = 0.0

    # All trades
    trades: List[BacktestTrade] = field(default_factory=list)

    # Equity curve
    equity_curve: List[Tuple[datetime, Decimal]] = field(default_factory=list)
