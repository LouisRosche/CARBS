"""
Sentiment Aggregator

Aggregates sentiment from multiple sources with trend detection.
"""

import json
import logging
from collections import deque
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List

from .enums import SentimentLevel
from .models import SentimentDataPoint, NewsItem
from .clients import CoinMarketCapClient, CryptoCompareClient

logger = logging.getLogger(__name__)


class SentimentAggregator:
    """
    Aggregates sentiment from multiple sources

    Maintains historical data for:
    - Trend detection
    - Divergence analysis
    - Velocity measurement
    """

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data/signals")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Data sources
        self.cmc_client = CoinMarketCapClient()
        self.cc_client = CryptoCompareClient()

        # Historical data (in-memory, persisted periodically)
        self._sentiment_history: Dict[str, deque] = {}  # asset -> deque of points
        self._news_cache: deque = deque(maxlen=1000)

        # Configuration
        self.history_window = 168  # 7 days of hourly data

        self._load_history()

    def _load_history(self):
        """Load historical data from disk"""
        history_file = self.data_dir / "sentiment_history.json"
        if history_file.exists():
            try:
                with open(history_file) as f:
                    data = json.load(f)
                    for asset, points in data.items():
                        self._sentiment_history[asset] = deque(maxlen=self.history_window)
                        for p in points:
                            self._sentiment_history[asset].append(
                                SentimentDataPoint(
                                    timestamp=datetime.fromisoformat(p["timestamp"]),
                                    source=p["source"],
                                    asset=p["asset"],
                                    score=p["score"],
                                    metadata=p.get("metadata", {})
                                )
                            )
            except Exception as e:
                logger.error(f"Failed to load sentiment history: {e}")

    def _save_history(self):
        """Persist historical data"""
        history_file = self.data_dir / "sentiment_history.json"
        data = {}
        for asset, points in self._sentiment_history.items():
            data[asset] = [
                {
                    "timestamp": p.timestamp.isoformat(),
                    "source": p.source,
                    "asset": p.asset,
                    "score": p.score,
                    "metadata": p.metadata
                }
                for p in points
            ]

        with open(history_file, 'w') as f:
            json.dump(data, f)

    async def update_all_sources(self) -> Dict[str, SentimentDataPoint]:
        """
        Fetch latest data from all sources

        Returns dict of asset -> latest sentiment
        """
        results = {}

        # Fear & Greed Index (market overall)
        fg_data = await self.cmc_client.get_fear_greed_index()
        if fg_data:
            self._add_to_history(fg_data)
            results["MARKET"] = fg_data

        # CryptoCompare news (affects individual assets)
        news = await self.cc_client.get_latest_news(limit=50)
        for item in news:
            self._news_cache.append(item)

        # Aggregate news sentiment by asset
        news_sentiment = self._aggregate_news_sentiment(news)
        for asset, score in news_sentiment.items():
            point = SentimentDataPoint(
                timestamp=datetime.now(timezone.utc),
                source="news_aggregate",
                asset=asset,
                score=self._normalize_sentiment(score),
                metadata={"article_count": len([n for n in news if asset in n.assets])}
            )
            self._add_to_history(point)
            results[asset] = point

        self._save_history()
        return results

    def _add_to_history(self, point: SentimentDataPoint):
        """Add data point to history"""
        if point.asset not in self._sentiment_history:
            self._sentiment_history[point.asset] = deque(maxlen=self.history_window)
        self._sentiment_history[point.asset].append(point)

    def _aggregate_news_sentiment(self, news: List[NewsItem]) -> Dict[str, float]:
        """
        Aggregate news sentiment by asset

        Weighted by importance and recency
        """
        asset_scores: Dict[str, List[tuple]] = {}  # asset -> [(score, weight)]

        now = datetime.now(timezone.utc)

        for item in news:
            # Time decay weight
            age_hours = (now - item.timestamp).total_seconds() / 3600
            time_weight = max(0.1, 1.0 - (age_hours / 24))  # Decay over 24 hours

            weight = item.importance * time_weight

            for asset in item.assets:
                if asset not in asset_scores:
                    asset_scores[asset] = []
                asset_scores[asset].append((item.sentiment_score, weight))

        # Weighted average
        result = {}
        for asset, scores in asset_scores.items():
            if scores:
                total_weight = sum(w for _, w in scores)
                if total_weight > 0:
                    result[asset] = sum(s * w for s, w in scores) / total_weight

        return result

    def _normalize_sentiment(self, score: float) -> float:
        """Normalize sentiment from -1,1 to 0-100"""
        return (score + 1) * 50

    def get_sentiment_momentum(self, asset: str, hours: int = 24) -> float:
        """
        Calculate sentiment momentum (rate of change)

        Returns: Positive = improving, Negative = worsening
        """
        if asset not in self._sentiment_history:
            return 0.0

        history = list(self._sentiment_history[asset])
        if len(history) < 2:
            return 0.0

        # Filter to time window
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent = [p for p in history if p.timestamp > cutoff]

        if len(recent) < 2:
            return 0.0

        # Linear regression slope
        n = len(recent)
        x_vals = list(range(n))
        y_vals = [p.score for p in recent]

        x_mean = sum(x_vals) / n
        y_mean = sum(y_vals) / n

        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals))
        denominator = sum((x - x_mean) ** 2 for x in x_vals)

        if denominator == 0:
            return 0.0

        slope = numerator / denominator
        return slope

    def get_sentiment_level(self, asset: str) -> SentimentLevel:
        """Get current sentiment level classification"""
        if asset not in self._sentiment_history:
            return SentimentLevel.NEUTRAL

        history = self._sentiment_history[asset]
        if not history:
            return SentimentLevel.NEUTRAL

        latest = history[-1].score

        if latest <= 20:
            return SentimentLevel.EXTREME_FEAR
        elif latest <= 40:
            return SentimentLevel.FEAR
        elif latest <= 60:
            return SentimentLevel.NEUTRAL
        elif latest <= 80:
            return SentimentLevel.GREED
        else:
            return SentimentLevel.EXTREME_GREED

    def get_news_velocity(self, asset: str, hours: int = 6) -> Dict:
        """
        Measure unusual news activity

        Returns:
            - count: Number of articles
            - velocity: Articles per hour
            - is_unusual: True if > 2 std dev from normal
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent_news = [
            n for n in self._news_cache
            if n.timestamp > cutoff and asset in n.assets
        ]

        count = len(recent_news)
        velocity = count / hours

        # Compare to historical average (simple heuristic)
        normal_velocity = 0.5  # Assume 0.5 articles/hour is normal
        is_unusual = velocity > normal_velocity * 3

        return {
            "count": count,
            "velocity": velocity,
            "is_unusual": is_unusual,
            "categories": self._categorize_recent_news(recent_news)
        }

    def _categorize_recent_news(self, news: List[NewsItem]) -> Dict[str, int]:
        """Count news by category"""
        counts = {}
        for item in news:
            cat = item.category.value
            counts[cat] = counts.get(cat, 0) + 1
        return counts
