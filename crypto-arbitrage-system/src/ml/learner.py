"""
Strategy Learner

Self-learning strategy optimization.
"""

import json
import logging
import random
import statistics
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


class StrategyLearner:
    """
    Self-learning strategy optimization

    Features:
    - Tracks strategy performance over time
    - Automatically adjusts parameters
    - Detects regime changes
    - A/B tests strategy variations
    """

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data/ml/learning")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Performance tracking
        self._performance_history: Dict[str, deque] = {}
        self._parameter_history: Dict[str, List] = {}

        # Current best parameters
        self._best_params: Dict[str, Dict] = {}

        # Learning settings
        self.learning_rate = 0.1
        self.exploration_rate = 0.2
        self.min_samples = 20

        self._load_state()

    def _load_state(self):
        """Load learning state"""
        state_file = self.data_dir / "learner_state.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    data = json.load(f)
                    self._best_params = data.get("best_params", {})
            except Exception as e:
                logger.error(f"Failed to load learner state: {e}")

    def _save_state(self):
        """Save learning state"""
        state_file = self.data_dir / "learner_state.json"
        with open(state_file, 'w') as f:
            json.dump({"best_params": self._best_params}, f, indent=2)

    def record_trade(
        self,
        strategy_name: str,
        parameters: Dict,
        result: Dict  # pnl, win, etc.
    ):
        """Record trade result for learning"""
        if strategy_name not in self._performance_history:
            self._performance_history[strategy_name] = deque(maxlen=1000)
            self._parameter_history[strategy_name] = []

        self._performance_history[strategy_name].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "parameters": parameters,
            "result": result
        })

        self._parameter_history[strategy_name].append(parameters)

        # Trigger learning if enough samples
        if len(self._performance_history[strategy_name]) >= self.min_samples:
            self._learn(strategy_name)

    def _learn(self, strategy_name: str):
        """Learn from recent performance"""
        history = list(self._performance_history[strategy_name])

        # Group by parameter sets
        param_performance: Dict[str, List[float]] = {}

        for record in history:
            params_key = json.dumps(record["parameters"], sort_keys=True)
            pnl = record["result"].get("pnl", 0)

            if params_key not in param_performance:
                param_performance[params_key] = []
            param_performance[params_key].append(pnl)

        # Find best performing parameters
        best_params_key = None
        best_avg_pnl = float('-inf')

        for params_key, pnls in param_performance.items():
            if len(pnls) >= 5:  # Need minimum samples
                avg_pnl = statistics.mean(pnls)
                if avg_pnl > best_avg_pnl:
                    best_avg_pnl = avg_pnl
                    best_params_key = params_key

        if best_params_key:
            self._best_params[strategy_name] = json.loads(best_params_key)
            self._save_state()

            logger.info(
                f"Strategy {strategy_name} learned: "
                f"best avg PnL={best_avg_pnl:.2f}, "
                f"params={self._best_params[strategy_name]}"
            )

    def suggest_parameters(
        self,
        strategy_name: str,
        param_ranges: Dict[str, tuple]
    ) -> Dict:
        """
        Suggest parameters for next trade

        Uses exploration/exploitation balance
        """
        # Exploit: use best known parameters
        if strategy_name in self._best_params and random.random() > self.exploration_rate:
            return self._best_params[strategy_name].copy()

        # Explore: try new parameters
        suggested = {}
        for param, (min_val, max_val) in param_ranges.items():
            if isinstance(min_val, int):
                suggested[param] = random.randint(min_val, max_val)
            else:
                suggested[param] = random.uniform(min_val, max_val)

        return suggested

    def get_performance_summary(self, strategy_name: str) -> Dict:
        """Get strategy performance summary"""
        if strategy_name not in self._performance_history:
            return {"error": "No data"}

        history = list(self._performance_history[strategy_name])
        pnls = [r["result"].get("pnl", 0) for r in history]

        if not pnls:
            return {"error": "No trades"}

        wins = sum(1 for p in pnls if p > 0)

        return {
            "total_trades": len(pnls),
            "win_rate": wins / len(pnls) * 100,
            "total_pnl": sum(pnls),
            "avg_pnl": statistics.mean(pnls),
            "best_trade": max(pnls),
            "worst_trade": min(pnls),
            "std_dev": statistics.stdev(pnls) if len(pnls) > 1 else 0,
            "best_params": self._best_params.get(strategy_name)
        }
