"""
Monte Carlo Simulator

Monte Carlo simulation for strategy robustness testing.
"""

import random
import statistics
from decimal import Decimal
from typing import Dict, List

from .models import BacktestTrade


class MonteCarloSimulator:
    """
    Monte Carlo simulation for strategy robustness

    Tests strategy performance under:
    - Random trade order shuffling
    - Return distribution sampling
    - Regime changes
    """

    def __init__(self, n_simulations: int = 1000):
        self.n_simulations = n_simulations

    def run_trade_shuffle(self, trades: List[BacktestTrade], initial_capital: Decimal) -> Dict:
        """
        Shuffle trade order to test path dependency

        A robust strategy should perform similarly regardless of trade order.
        """
        original_pnls = [float(t.pnl or 0) for t in trades]

        final_capitals = []

        for _ in range(self.n_simulations):
            shuffled = original_pnls.copy()
            random.shuffle(shuffled)

            capital = float(initial_capital)
            for pnl in shuffled:
                capital += pnl
                if capital <= 0:
                    capital = 0
                    break

            final_capitals.append(capital)

        return {
            "original_final": float(initial_capital) + sum(original_pnls),
            "mean_final": statistics.mean(final_capitals),
            "std_final": statistics.stdev(final_capitals),
            "min_final": min(final_capitals),
            "max_final": max(final_capitals),
            "probability_of_ruin": sum(1 for c in final_capitals if c <= 0) / self.n_simulations,
            "confidence_95_lower": sorted(final_capitals)[int(0.025 * len(final_capitals))],
            "confidence_95_upper": sorted(final_capitals)[int(0.975 * len(final_capitals))]
        }

    def run_bootstrap(self, daily_returns: List[float], initial_capital: float, days: int = 252) -> Dict:
        """
        Bootstrap simulation of future returns

        Samples from historical return distribution to project future outcomes.
        """
        simulations = []

        for _ in range(self.n_simulations):
            capital = initial_capital
            path = [capital]

            for _ in range(days):
                daily_return = random.choice(daily_returns)
                capital *= (1 + daily_return)
                path.append(capital)

            simulations.append({
                "final_capital": capital,
                "max_drawdown": self._calculate_max_drawdown(path),
                "path": path
            })

        final_capitals = [s["final_capital"] for s in simulations]
        drawdowns = [s["max_drawdown"] for s in simulations]

        return {
            "mean_final": statistics.mean(final_capitals),
            "median_final": statistics.median(final_capitals),
            "std_final": statistics.stdev(final_capitals),
            "var_95": sorted(final_capitals)[int(0.05 * len(final_capitals))],
            "cvar_95": statistics.mean(sorted(final_capitals)[:int(0.05 * len(final_capitals))]),
            "mean_max_drawdown": statistics.mean(drawdowns),
            "probability_of_loss": sum(1 for c in final_capitals if c < initial_capital) / self.n_simulations
        }

    def _calculate_max_drawdown(self, path: List[float]) -> float:
        """Calculate max drawdown from equity path"""
        peak = path[0]
        max_dd = 0

        for value in path:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)

        return max_dd
