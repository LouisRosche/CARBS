"""
Regime Detector

Market regime detection for strategy adaptation.
"""

import statistics
from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import Dict


class Regime(Enum):
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOL = "high_volatility"
    LOW_VOL = "low_volatility"
    UNKNOWN = "unknown"


class RegimeDetector:
    """
    Market regime detection

    Detects:
    - Bull market
    - Bear market
    - Sideways/ranging
    - High volatility
    - Low volatility
    """

    def __init__(self, lookback_days: int = 30):
        self.lookback_days = lookback_days
        self._price_history: deque = deque(maxlen=lookback_days * 24)  # Hourly
        self._current_regime = Regime.UNKNOWN

    def update(self, price: float, timestamp: datetime = None):
        """Update with new price"""
        self._price_history.append({
            "price": price,
            "timestamp": timestamp or datetime.now(timezone.utc)
        })

        if len(self._price_history) >= 24:  # Need at least 24 hours
            self._current_regime = self._detect_regime()

    def _detect_regime(self) -> Regime:
        """Detect current regime"""
        prices = [p["price"] for p in self._price_history]

        if len(prices) < 24:
            return Regime.UNKNOWN

        # Calculate returns
        returns = [(prices[i] - prices[i-1]) / prices[i-1]
                   for i in range(1, len(prices))]

        # Trend detection
        avg_return = statistics.mean(returns)
        volatility = statistics.stdev(returns) if len(returns) > 1 else 0

        # Price change over period
        price_change = (prices[-1] - prices[0]) / prices[0]

        # Classify
        if volatility > 0.03:  # High volatility threshold
            return Regime.HIGH_VOL
        elif volatility < 0.005:  # Low volatility threshold
            return Regime.LOW_VOL
        elif price_change > 0.1:  # 10% up
            return Regime.BULL
        elif price_change < -0.1:  # 10% down
            return Regime.BEAR
        else:
            return Regime.SIDEWAYS

    @property
    def current_regime(self) -> Regime:
        return self._current_regime

    def get_strategy_adjustment(self) -> Dict:
        """Get strategy adjustments for current regime"""
        adjustments = {
            Regime.BULL: {
                "bias": "long",
                "position_size_multiplier": 1.2,
                "stop_loss_multiplier": 1.1,  # Wider stops
                "take_profit_multiplier": 1.3  # Larger targets
            },
            Regime.BEAR: {
                "bias": "short",
                "position_size_multiplier": 0.8,  # Smaller positions
                "stop_loss_multiplier": 0.9,  # Tighter stops
                "take_profit_multiplier": 0.8
            },
            Regime.SIDEWAYS: {
                "bias": "neutral",
                "position_size_multiplier": 0.7,
                "stop_loss_multiplier": 0.8,
                "take_profit_multiplier": 0.7
            },
            Regime.HIGH_VOL: {
                "bias": "neutral",
                "position_size_multiplier": 0.5,  # Reduce size in high vol
                "stop_loss_multiplier": 1.5,  # Much wider stops
                "take_profit_multiplier": 1.5
            },
            Regime.LOW_VOL: {
                "bias": "neutral",
                "position_size_multiplier": 1.0,
                "stop_loss_multiplier": 0.7,  # Tighter in low vol
                "take_profit_multiplier": 0.7
            }
        }

        return adjustments.get(self._current_regime, {
            "bias": "neutral",
            "position_size_multiplier": 1.0,
            "stop_loss_multiplier": 1.0,
            "take_profit_multiplier": 1.0
        })
