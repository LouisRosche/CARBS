"""
Walk-Forward Optimizer

Walk-forward optimization for robust parameter selection.
"""

import json
import logging
import statistics
from datetime import datetime, timedelta
from typing import Callable, Dict, List

from .enums import TimeFrame
from .engine import BacktestEngine

logger = logging.getLogger(__name__)


class WalkForwardOptimizer:
    """
    Walk-forward optimization for robust parameter selection

    Prevents overfitting by:
    1. Dividing data into train/test windows
    2. Optimizing on train, validating on test
    3. Rolling forward through time
    """

    def __init__(
        self,
        engine: BacktestEngine,
        train_size: int = 30,  # days
        test_size: int = 10,   # days
        step_size: int = 10    # days to roll forward
    ):
        self.engine = engine
        self.train_size = train_size
        self.test_size = test_size
        self.step_size = step_size

    async def optimize(
        self,
        strategy: Callable,
        asset: str,
        timeframe: TimeFrame,
        start: datetime,
        end: datetime,
        param_grid: Dict[str, List],
        metric: str = "sharpe_ratio"
    ) -> Dict:
        """
        Run walk-forward optimization

        Returns:
            Best parameters and aggregated results
        """
        results = []
        current_start = start

        while current_start + timedelta(days=self.train_size + self.test_size) <= end:
            train_end = current_start + timedelta(days=self.train_size)
            test_end = train_end + timedelta(days=self.test_size)

            # Find best params on training data
            best_params = None
            best_score = float('-inf')

            for params in self._generate_param_combinations(param_grid):
                result = await self.engine.run(
                    strategy=strategy,
                    asset=asset,
                    timeframe=timeframe,
                    start=current_start,
                    end=train_end,
                    strategy_params=params
                )

                score = getattr(result, metric, 0)
                if score > best_score:
                    best_score = score
                    best_params = params

            # Validate on test data
            if best_params:
                test_result = await self.engine.run(
                    strategy=strategy,
                    asset=asset,
                    timeframe=timeframe,
                    start=train_end,
                    end=test_end,
                    strategy_params=best_params
                )

                results.append({
                    "train_period": (current_start, train_end),
                    "test_period": (train_end, test_end),
                    "best_params": best_params,
                    "train_score": best_score,
                    "test_score": getattr(test_result, metric, 0),
                    "test_result": test_result
                })

            current_start += timedelta(days=self.step_size)

        # Aggregate results
        return self._aggregate_results(results, metric)

    def _generate_param_combinations(self, param_grid: Dict) -> List[Dict]:
        """Generate all parameter combinations"""
        if not param_grid:
            return [{}]

        keys = list(param_grid.keys())
        values = list(param_grid.values())

        combinations = []

        def _recurse(idx, current):
            if idx == len(keys):
                combinations.append(dict(current))
                return
            for val in values[idx]:
                current[keys[idx]] = val
                _recurse(idx + 1, current)

        _recurse(0, {})
        return combinations

    def _aggregate_results(self, results: List[Dict], metric: str) -> Dict:
        """Aggregate walk-forward results"""
        if not results:
            return {"error": "No results"}

        # Find most robust parameters (best avg test score)
        param_scores: Dict[str, List[float]] = {}

        for r in results:
            params_key = json.dumps(r["best_params"], sort_keys=True)
            if params_key not in param_scores:
                param_scores[params_key] = []
            param_scores[params_key].append(r["test_score"])

        # Best by average
        best_params_key = max(param_scores.keys(), key=lambda k: statistics.mean(param_scores[k]))

        return {
            "best_params": json.loads(best_params_key),
            "avg_test_score": statistics.mean(param_scores[best_params_key]),
            "test_score_std": statistics.stdev(param_scores[best_params_key]) if len(param_scores[best_params_key]) > 1 else 0,
            "num_windows": len(results),
            "consistency": sum(1 for r in results if r["test_score"] > 0) / len(results),
            "all_results": results
        }
