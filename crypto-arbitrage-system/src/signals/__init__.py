"""
News & Sentiment Signal System

Multi-source sentiment aggregation for crypto trading signals:
- CoinMarketCap Fear & Greed Index (free)
- CryptoCompare News & Social (free tier)
- LunarCrush social metrics (free tier)
- Custom RSS/news scraping
- Extensible for paid APIs (The Tie, StockGeist, Santiment)

Signal generation combines:
- Sentiment momentum (rate of change)
- Sentiment divergence (price vs sentiment)
- News velocity (unusual activity detection)
- Fear/greed extremes (contrarian signals)
"""

import asyncio
import aiohttp
import hashlib
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from collections import deque
import json
import statistics

logger = logging.getLogger(__name__)


class SentimentLevel(Enum):
    """Sentiment classification"""
    EXTREME_FEAR = "extreme_fear"      # 0-20
    FEAR = "fear"                       # 21-40
    NEUTRAL = "neutral"                 # 41-60
    GREED = "greed"                     # 61-80
    EXTREME_GREED = "extreme_greed"    # 81-100


class SignalType(Enum):
    """Trading signal types"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class NewsCategory(Enum):
    """News categorization"""
    REGULATORY = "regulatory"
    ADOPTION = "adoption"
    TECHNOLOGY = "technology"
    MARKET = "market"
    SECURITY = "security"  # Hacks, exploits
    MACRO = "macro"        # Fed, inflation, etc.
    WHALE = "whale"        # Large movements
    UNKNOWN = "unknown"


@dataclass
class SentimentDataPoint:
    """Single sentiment measurement"""
    timestamp: datetime
    source: str
    asset: str  # "BTC", "ETH", "MARKET" for overall
    score: float  # 0-100 normalized
    raw_value: Any = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class NewsItem:
    """Parsed news item"""
    news_id: str
    timestamp: datetime
    source: str
    title: str
    url: str
    assets: List[str]  # Mentioned assets
    category: NewsCategory
    sentiment_score: float  # -1 to 1
    importance: float  # 0 to 1
    raw_content: str = ""


@dataclass
class TradingSignal:
    """Generated trading signal"""
    signal_id: str
    timestamp: datetime
    asset: str
    signal_type: SignalType
    confidence: float  # 0-1
    reasons: List[str]
    sentiment_score: float
    price_at_signal: float = None

    # For tracking
    expires_at: datetime = None
    triggered_trade_id: str = None


class CoinMarketCapClient:
    """
    CoinMarketCap Fear & Greed Index client

    Free tier: Basic fear/greed data
    """

    BASE_URL = "https://api.coinmarketcap.com"

    # Scrape the public chart data (no API key needed)
    FEAR_GREED_URL = "https://api.alternative.me/fng/"

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self._cache: Dict[str, tuple] = {}  # (data, timestamp)
        self._cache_ttl = 300  # 5 minutes

    async def get_fear_greed_index(self) -> SentimentDataPoint:
        """
        Get current Fear & Greed Index

        Uses alternative.me API (free, no key needed)
        """
        cache_key = "fear_greed"

        # Check cache
        if cache_key in self._cache:
            data, cached_at = self._cache[cache_key]
            if datetime.now(timezone.utc) - cached_at < timedelta(seconds=self._cache_ttl):
                return data

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.FEAR_GREED_URL,
                    params={"limit": 1, "format": "json"}
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()

                        if result.get("data"):
                            item = result["data"][0]

                            data_point = SentimentDataPoint(
                                timestamp=datetime.fromtimestamp(
                                    int(item["timestamp"]),
                                    tz=timezone.utc
                                ),
                                source="fear_greed_index",
                                asset="MARKET",
                                score=float(item["value"]),
                                raw_value=item,
                                metadata={
                                    "classification": item["value_classification"],
                                    "time_until_update": item.get("time_until_update")
                                }
                            )

                            self._cache[cache_key] = (data_point, datetime.now(timezone.utc))
                            return data_point

        except Exception as e:
            logger.error(f"Failed to fetch Fear & Greed Index: {e}")

        return None

    async def get_historical_fear_greed(self, days: int = 30) -> List[SentimentDataPoint]:
        """Get historical Fear & Greed data"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.FEAR_GREED_URL,
                    params={"limit": days, "format": "json"}
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()

                        points = []
                        for item in result.get("data", []):
                            points.append(SentimentDataPoint(
                                timestamp=datetime.fromtimestamp(
                                    int(item["timestamp"]),
                                    tz=timezone.utc
                                ),
                                source="fear_greed_index",
                                asset="MARKET",
                                score=float(item["value"]),
                                raw_value=item,
                                metadata={"classification": item["value_classification"]}
                            ))

                        return points

        except Exception as e:
            logger.error(f"Failed to fetch historical Fear & Greed: {e}")

        return []


class CryptoCompareClient:
    """
    CryptoCompare API client

    Free tier includes:
    - News feed
    - Social stats
    - Basic price data
    """

    BASE_URL = "https://min-api.cryptocompare.com"
    NEWS_URL = "https://min-api.cryptocompare.com/data/v2/news/"

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self._headers = {}
        if api_key:
            self._headers["authorization"] = f"Apikey {api_key}"

    async def get_latest_news(
        self,
        categories: List[str] = None,
        limit: int = 50
    ) -> List[NewsItem]:
        """
        Fetch latest crypto news

        Categories: Blockchain, Exchange, Mining, Trading, etc.
        """
        params = {"lang": "EN"}
        if categories:
            params["categories"] = ",".join(categories)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.NEWS_URL,
                    params=params,
                    headers=self._headers
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()

                        items = []
                        for article in result.get("Data", [])[:limit]:
                            # Extract mentioned assets from tags
                            assets = []
                            if article.get("tags"):
                                # Common crypto symbols
                                for tag in article["tags"].split("|"):
                                    tag = tag.strip().upper()
                                    if tag in ["BTC", "ETH", "SOL", "XRP", "DOGE",
                                               "ADA", "AVAX", "DOT", "MATIC", "LINK"]:
                                        assets.append(tag)

                            # Categorize
                            category = self._categorize_news(
                                article.get("title", ""),
                                article.get("body", ""),
                                article.get("categories", "")
                            )

                            # Simple sentiment from title
                            sentiment = self._quick_sentiment(article.get("title", ""))

                            items.append(NewsItem(
                                news_id=str(article.get("id", "")),
                                timestamp=datetime.fromtimestamp(
                                    article.get("published_on", 0),
                                    tz=timezone.utc
                                ),
                                source=article.get("source", "cryptocompare"),
                                title=article.get("title", ""),
                                url=article.get("url", ""),
                                assets=assets if assets else ["MARKET"],
                                category=category,
                                sentiment_score=sentiment,
                                importance=self._calc_importance(article),
                                raw_content=article.get("body", "")[:500]
                            ))

                        return items

        except Exception as e:
            logger.error(f"Failed to fetch CryptoCompare news: {e}")

        return []

    def _categorize_news(self, title: str, body: str, categories: str) -> NewsCategory:
        """Categorize news article"""
        text = f"{title} {body} {categories}".lower()

        if any(w in text for w in ["sec", "regulation", "ban", "legal", "lawsuit", "court"]):
            return NewsCategory.REGULATORY
        elif any(w in text for w in ["hack", "exploit", "breach", "stolen", "vulnerability"]):
            return NewsCategory.SECURITY
        elif any(w in text for w in ["adopt", "accept", "partnership", "integration"]):
            return NewsCategory.ADOPTION
        elif any(w in text for w in ["upgrade", "fork", "protocol", "mainnet", "testnet"]):
            return NewsCategory.TECHNOLOGY
        elif any(w in text for w in ["whale", "transfer", "moved", "billion", "million usd"]):
            return NewsCategory.WHALE
        elif any(w in text for w in ["fed", "inflation", "rates", "economy", "recession"]):
            return NewsCategory.MACRO
        else:
            return NewsCategory.MARKET

    def _quick_sentiment(self, title: str) -> float:
        """
        Quick sentiment analysis from title
        Returns -1 to 1
        """
        title_lower = title.lower()

        positive_words = [
            "surge", "soar", "rally", "bullish", "gains", "breakthrough",
            "adoption", "partnership", "upgrade", "success", "record",
            "moon", "pump", "growth", "profit", "win"
        ]

        negative_words = [
            "crash", "plunge", "dump", "bearish", "losses", "hack",
            "ban", "regulation", "lawsuit", "fear", "sell-off",
            "decline", "drop", "fail", "scam", "fraud"
        ]

        pos_count = sum(1 for w in positive_words if w in title_lower)
        neg_count = sum(1 for w in negative_words if w in title_lower)

        if pos_count == 0 and neg_count == 0:
            return 0.0

        return (pos_count - neg_count) / (pos_count + neg_count)

    def _calc_importance(self, article: Dict) -> float:
        """Calculate article importance 0-1"""
        importance = 0.5

        # Source reputation boost
        reputable = ["coindesk", "cointelegraph", "decrypt", "theblock"]
        if any(s in article.get("source", "").lower() for s in reputable):
            importance += 0.2

        # Recency boost
        age_hours = (datetime.now(timezone.utc).timestamp() -
                     article.get("published_on", 0)) / 3600
        if age_hours < 1:
            importance += 0.2
        elif age_hours < 6:
            importance += 0.1

        return min(1.0, importance)

    async def get_social_stats(self, symbol: str) -> Dict:
        """Get social media statistics for a coin"""
        url = f"{self.BASE_URL}/data/social/coin/latest"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params={"coinId": self._get_coin_id(symbol)},
                    headers=self._headers
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get("Data", {})

        except Exception as e:
            logger.error(f"Failed to fetch social stats for {symbol}: {e}")

        return {}

    def _get_coin_id(self, symbol: str) -> int:
        """Map symbol to CryptoCompare coin ID"""
        # Common mappings
        ids = {
            "BTC": 1182,
            "ETH": 7605,
            "SOL": 934443,
            "XRP": 5031,
            "DOGE": 4432
        }
        return ids.get(symbol.upper(), 1182)  # Default to BTC


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
        # In production, would track rolling averages
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


class SignalService:
    """
    Main service orchestrating signal generation

    Runs continuously, updating sentiment and generating signals.
    """

    def __init__(
        self,
        data_dir: Path = None,
        alert_callback: Callable = None,
        update_interval: int = 300  # 5 minutes
    ):
        self.data_dir = data_dir or Path("data/signals")
        self.alert_callback = alert_callback
        self.update_interval = update_interval

        self.aggregator = SentimentAggregator(data_dir=self.data_dir)
        self.generator = SignalGenerator(
            aggregator=self.aggregator,
            alert_callback=alert_callback
        )

        self._running = False
        self._task = None

    async def start(self):
        """Start the signal service"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Signal service started")

    async def stop(self):
        """Stop the signal service"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Signal service stopped")

    async def _run_loop(self):
        """Main service loop"""
        while self._running:
            try:
                # Generate signals for main assets
                signals = await self.generator.generate_signals(
                    assets=["BTC", "ETH", "SOL"],
                    include_market=True
                )

                if signals:
                    logger.info(f"Generated {len(signals)} signals")
                    for signal in signals:
                        logger.info(
                            f"  {signal.asset}: {signal.signal_type.value} "
                            f"(confidence: {signal.confidence:.0%})"
                        )

            except Exception as e:
                logger.error(f"Error in signal loop: {e}")

            await asyncio.sleep(self.update_interval)

    async def get_current_sentiment(self) -> Dict:
        """Get current sentiment summary"""
        await self.aggregator.update_all_sources()

        summary = {}
        for asset in ["MARKET", "BTC", "ETH", "SOL"]:
            level = self.aggregator.get_sentiment_level(asset)
            momentum = self.aggregator.get_sentiment_momentum(asset)
            history = self.aggregator._sentiment_history.get(asset, [])

            summary[asset] = {
                "level": level.value,
                "score": history[-1].score if history else None,
                "momentum": momentum,
                "trend": "improving" if momentum > 0.5 else "declining" if momentum < -0.5 else "stable"
            }

        return summary

    def get_signals(self) -> List[TradingSignal]:
        """Get active trading signals"""
        return self.generator.get_active_signals()


# Factory function
def create_signal_service(
    data_dir: Path = None,
    alert_callback: Callable = None
) -> SignalService:
    """Create and configure signal service"""
    return SignalService(
        data_dir=data_dir,
        alert_callback=alert_callback
    )


__all__ = [
    "SentimentLevel",
    "SignalType",
    "NewsCategory",
    "SentimentDataPoint",
    "NewsItem",
    "TradingSignal",
    "CoinMarketCapClient",
    "CryptoCompareClient",
    "SentimentAggregator",
    "SignalGenerator",
    "SignalService",
    "create_signal_service"
]
