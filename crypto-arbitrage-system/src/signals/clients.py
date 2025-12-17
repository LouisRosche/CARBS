"""
Signal Clients

API clients for sentiment data sources.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List

import aiohttp

from .enums import NewsCategory
from .models import SentimentDataPoint, NewsItem

logger = logging.getLogger(__name__)


class CoinMarketCapClient:
    """
    CoinMarketCap Fear & Greed Index client

    Free tier: Basic fear/greed data
    """

    BASE_URL = "https://api.coinmarketcap.com"
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
        """Quick sentiment analysis from title. Returns -1 to 1"""
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
        ids = {
            "BTC": 1182,
            "ETH": 7605,
            "SOL": 934443,
            "XRP": 5031,
            "DOGE": 4432
        }
        return ids.get(symbol.upper(), 1182)  # Default to BTC
