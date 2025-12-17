"""
Backtesting Framework

Production-grade backtesting with:
- Historical data management
- Realistic simulation (fees, slippage, latency)
- Walk-forward optimization
- Monte Carlo robustness testing
- Performance analytics
- Anti-fragility metrics

Module Structure:
- enums.py: TimeFrame
- models.py: OHLCV, BacktestTrade, BacktestResult
- data_manager.py: HistoricalDataManager
- engine.py: BacktestEngine
- optimizer.py: WalkForwardOptimizer
- monte_carlo.py: MonteCarloSimulator
- strategies.py: Example strategies
"""

# Import from submodules for backward compatibility
from .enums import TimeFrame
from .models import OHLCV, BacktestTrade, BacktestResult
from .data_manager import HistoricalDataManager
from .engine import BacktestEngine
from .optimizer import WalkForwardOptimizer
from .monte_carlo import MonteCarloSimulator
from .strategies import momentum_strategy


__all__ = [
    # Enums
    "TimeFrame",

    # Models
    "OHLCV",
    "BacktestTrade",
    "BacktestResult",

    # Core classes
    "HistoricalDataManager",
    "BacktestEngine",
    "WalkForwardOptimizer",
    "MonteCarloSimulator",

    # Example strategies
    "momentum_strategy",
]
