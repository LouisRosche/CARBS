"""
Signal Generator

Generates trading signals from sentiment data.
"""

import hashlib
import logging
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Callable, List, Optional

from .enums import SentimentLevel, SignalType
from .models import TradingSignal
from .aggregator import SentimentAggregator

logger = logging.getLogger(__name__)


class SignalGenerator:
    """
    Generates trading signals from sentiment data

    Strategies:
    1. Extreme fear = contrarian buy
    2. Extreme greed = contrarian sell
    3. Sentiment momentum shifts
    4. News velocity spikes
    5. Sentiment-price divergence
    """

    def __init__(
        self,
        aggregator: SentimentAggregator,
        alert_callback: Callable = None
    ):
        self.aggregator = aggregator
        self.alert_callback = alert_callback

        # Signal history
        self._signals: deque = deque(maxlen=1000)

        # Thresholds (configurable)
        self.extreme_fear_threshold = 20
        self.extreme_greed_threshold = 80
        self.momentum_threshold = 2.0  # Points per hour
        self.min_confidence = 0.6

    async def generate_signals(
        self,
        assets: List[str] = None,
        include_market: bool = True
    ) -> List[TradingSignal]:
        """
        Generate signals for specified assets

        Args:
            assets: List of assets to analyze
            include_market: Include overall market signal
        """
        if assets is None:
            assets = ["BTC", "ETH"]

        if include_market:
            assets = ["MARKET"] + assets

        signals = []

        # Update sentiment data
        await self.aggregator.update_all_sources()

        for asset in assets:
            signal = await self._analyze_asset(asset)
            if signal and signal.confidence >= self.min_confidence:
                signals.append(signal)
                self._signals.append(signal)

                # Alert on strong signals
                if self.alert_callback and signal.signal_type in [
                    SignalType.STRONG_BUY, SignalType.STRONG_SELL
                ]:
                    await self.alert_callback(
                        f"Signal: {signal.signal_type.value.upper()} {asset}",
                        f"Confidence: {signal.confidence:.0%}\n"
                        f"Reasons: {', '.join(signal.reasons)}\n"
                        f"Sentiment: {signal.sentiment_score:.0f}"
                    )

        return signals

    async def _analyze_asset(self, asset: str) -> Optional[TradingSignal]:
        """Analyze single asset for signals"""
        reasons = []
        score = 0  # Accumulate signal strength

        # 1. Check sentiment level
        level = self.aggregator.get_sentiment_level(asset)

        if level == SentimentLevel.EXTREME_FEAR:
            score += 2
            reasons.append(f"Extreme fear ({level.value})")
        elif level == SentimentLevel.FEAR:
            score += 1
            reasons.append(f"Fear ({level.value})")
        elif level == SentimentLevel.EXTREME_GREED:
            score -= 2
            reasons.append(f"Extreme greed ({level.value})")
        elif level == SentimentLevel.GREED:
            score -= 1
            reasons.append(f"Greed ({level.value})")

        # 2. Check momentum
        momentum = self.aggregator.get_sentiment_momentum(asset, hours=24)

        if momentum > self.momentum_threshold:
            score += 1
            reasons.append(f"Positive momentum (+{momentum:.1f}/hr)")
        elif momentum < -self.momentum_threshold:
            score -= 1
            reasons.append(f"Negative momentum ({momentum:.1f}/hr)")

        # 3. Check news velocity
        news_data = self.aggregator.get_news_velocity(asset, hours=6)

        if news_data["is_unusual"]:
            # Check if news is positive or negative
            categories = news_data["categories"]
            if categories.get("security", 0) > 0:
                score -= 1
                reasons.append(f"Security news spike ({news_data['count']} articles)")
            elif categories.get("adoption", 0) > categories.get("regulatory", 0):
                score += 1
                reasons.append(f"Adoption news spike ({news_data['count']} articles)")

        # 4. Contrarian signals at extremes
        if level == SentimentLevel.EXTREME_FEAR and momentum > 0:
            score += 1
            reasons.append("Fear with improving momentum (contrarian buy)")
        elif level == SentimentLevel.EXTREME_GREED and momentum < 0:
            score -= 1
            reasons.append("Greed with declining momentum (contrarian sell)")

        # No signal if score too weak
        if abs(score) < 1:
            return None

        # Determine signal type
        if score >= 3:
            signal_type = SignalType.STRONG_BUY
        elif score >= 1:
            signal_type = SignalType.BUY
        elif score <= -3:
            signal_type = SignalType.STRONG_SELL
        elif score <= -1:
            signal_type = SignalType.SELL
        else:
            signal_type = SignalType.NEUTRAL

        # Calculate confidence
        confidence = min(1.0, abs(score) / 4)

        # Get current sentiment score
        history = self.aggregator._sentiment_history.get(asset, [])
        sentiment_score = history[-1].score if history else 50.0

        return TradingSignal(
            signal_id=hashlib.sha256(
                f"{asset}:{datetime.now().isoformat()}".encode()
            ).hexdigest()[:16],
            timestamp=datetime.now(timezone.utc),
            asset=asset,
            signal_type=signal_type,
            confidence=confidence,
            reasons=reasons,
            sentiment_score=sentiment_score,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=4)
        )

    def get_active_signals(self) -> List[TradingSignal]:
        """Get currently active (non-expired) signals"""
        now = datetime.now(timezone.utc)
        return [
            s for s in self._signals
            if s.expires_at and s.expires_at > now
        ]
