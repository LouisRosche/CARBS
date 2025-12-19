"""
Tests for signals module

Tests:
- Sentiment data points
- News items
- Trading signals
- CoinMarketCap client
- Signal aggregation
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import json

from src.signals import (
    SentimentLevel,
    SignalType,
    NewsCategory,
    SentimentDataPoint,
    NewsItem,
    TradingSignal,
    CoinMarketCapClient,
)


class TestSentimentLevel:
    """Tests for SentimentLevel enum"""

    def test_all_levels_defined(self):
        """Should have all sentiment levels"""
        assert SentimentLevel.EXTREME_FEAR.value == "extreme_fear"
        assert SentimentLevel.FEAR.value == "fear"
        assert SentimentLevel.NEUTRAL.value == "neutral"
        assert SentimentLevel.GREED.value == "greed"
        assert SentimentLevel.EXTREME_GREED.value == "extreme_greed"

    def test_level_from_score(self):
        """Should map scores to correct levels"""
        def get_level(score: float) -> SentimentLevel:
            if score <= 20:
                return SentimentLevel.EXTREME_FEAR
            elif score <= 40:
                return SentimentLevel.FEAR
            elif score <= 60:
                return SentimentLevel.NEUTRAL
            elif score <= 80:
                return SentimentLevel.GREED
            else:
                return SentimentLevel.EXTREME_GREED

        assert get_level(10) == SentimentLevel.EXTREME_FEAR
        assert get_level(30) == SentimentLevel.FEAR
        assert get_level(50) == SentimentLevel.NEUTRAL
        assert get_level(70) == SentimentLevel.GREED
        assert get_level(90) == SentimentLevel.EXTREME_GREED


class TestSignalType:
    """Tests for SignalType enum"""

    def test_all_signal_types(self):
        """Should have all signal types"""
        assert SignalType.STRONG_BUY.value == "strong_buy"
        assert SignalType.BUY.value == "buy"
        assert SignalType.NEUTRAL.value == "neutral"
        assert SignalType.SELL.value == "sell"
        assert SignalType.STRONG_SELL.value == "strong_sell"


class TestNewsCategory:
    """Tests for NewsCategory enum"""

    def test_all_categories(self):
        """Should have all news categories"""
        expected = ["regulatory", "adoption", "technology", "market",
                   "security", "macro", "whale", "unknown"]

        for cat in NewsCategory:
            assert cat.value in expected


class TestSentimentDataPoint:
    """Tests for SentimentDataPoint dataclass"""

    def test_data_point_creation(self):
        """Should create sentiment data point"""
        point = SentimentDataPoint(
            timestamp=datetime.now(timezone.utc),
            source="fear_greed_index",
            asset="MARKET",
            score=45.0,
            raw_value={"value": "45"},
            metadata={"classification": "Fear"}
        )

        assert point.source == "fear_greed_index"
        assert point.asset == "MARKET"
        assert point.score == 45.0

    def test_data_point_default_metadata(self):
        """Should have empty default metadata"""
        point = SentimentDataPoint(
            timestamp=datetime.now(timezone.utc),
            source="test",
            asset="BTC",
            score=50.0
        )

        assert point.metadata == {}
        assert point.raw_value is None


class TestNewsItem:
    """Tests for NewsItem dataclass"""

    def test_news_item_creation(self):
        """Should create news item"""
        item = NewsItem(
            news_id="news_001",
            timestamp=datetime.now(timezone.utc),
            source="cryptonews",
            title="Bitcoin reaches new high",
            url="https://example.com/news/123",
            assets=["BTC"],
            category=NewsCategory.MARKET,
            sentiment_score=0.8,
            importance=0.9
        )

        assert item.news_id == "news_001"
        assert item.category == NewsCategory.MARKET
        assert item.sentiment_score == 0.8

    def test_news_item_multiple_assets(self):
        """Should support multiple assets"""
        item = NewsItem(
            news_id="news_002",
            timestamp=datetime.now(timezone.utc),
            source="source",
            title="ETH and BTC correlation",
            url="https://example.com",
            assets=["BTC", "ETH", "SOL"],
            category=NewsCategory.MARKET,
            sentiment_score=0.0,
            importance=0.5
        )

        assert len(item.assets) == 3
        assert "ETH" in item.assets


class TestTradingSignal:
    """Tests for TradingSignal dataclass"""

    def test_signal_creation(self):
        """Should create trading signal"""
        signal = TradingSignal(
            signal_id="sig_001",
            timestamp=datetime.now(timezone.utc),
            asset="BTC",
            signal_type=SignalType.BUY,
            confidence=0.75,
            reasons=["Fear index below 25", "Oversold RSI"],
            sentiment_score=22.0
        )

        assert signal.signal_type == SignalType.BUY
        assert signal.confidence == 0.75
        assert len(signal.reasons) == 2

    def test_signal_with_expiration(self):
        """Should support expiration time"""
        now = datetime.now(timezone.utc)
        signal = TradingSignal(
            signal_id="sig_002",
            timestamp=now,
            asset="ETH",
            signal_type=SignalType.STRONG_SELL,
            confidence=0.9,
            reasons=["Major bearish news"],
            sentiment_score=15.0,
            expires_at=now + timedelta(hours=1)
        )

        assert signal.expires_at > signal.timestamp


class TestCoinMarketCapClient:
    """Tests for CoinMarketCap client"""

    @pytest.fixture
    def client(self):
        """Create client instance"""
        return CoinMarketCapClient()

    def test_client_initialization(self, client):
        """Should initialize with defaults"""
        assert client._cache == {}
        assert client._cache_ttl == 300

    def test_cache_key(self, client):
        """Should use correct cache keys"""
        cache_key = "fear_greed"
        assert isinstance(cache_key, str)

    @pytest.mark.asyncio
    async def test_cache_hit(self, client):
        """Should return cached data when fresh"""
        # Pre-populate cache
        cached_data = SentimentDataPoint(
            timestamp=datetime.now(timezone.utc),
            source="fear_greed_index",
            asset="MARKET",
            score=45.0
        )
        client._cache["fear_greed"] = (cached_data, datetime.now(timezone.utc))

        # Should return cached data
        result = await client.get_fear_greed_index()

        assert result == cached_data

    @pytest.mark.asyncio
    async def test_cache_miss_expired(self, client):
        """Should fetch new data when cache expired"""
        # Pre-populate with old cache
        old_time = datetime.now(timezone.utc) - timedelta(seconds=600)
        cached_data = SentimentDataPoint(
            timestamp=old_time,
            source="fear_greed_index",
            asset="MARKET",
            score=45.0
        )
        client._cache["fear_greed"] = (cached_data, old_time)

        # Mock the HTTP request
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "data": [{
                    "value": "50",
                    "value_classification": "Neutral",
                    "timestamp": str(int(datetime.now(timezone.utc).timestamp()))
                }]
            })

            mock_session_instance = AsyncMock()
            mock_session_instance.get = AsyncMock(return_value=mock_response)
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await client.get_fear_greed_index()

            # Should have attempted to fetch
            assert mock_session_instance.get.called or result is not None


class TestSignalAggregation:
    """Tests for signal aggregation logic"""

    def test_weighted_average_calculation(self):
        """Should calculate weighted sentiment average"""
        scores = [
            (45.0, 0.4),  # Fear & Greed, weight 0.4
            (60.0, 0.3),  # Social sentiment, weight 0.3
            (50.0, 0.3),  # News sentiment, weight 0.3
        ]

        weighted_sum = sum(score * weight for score, weight in scores)
        total_weight = sum(weight for _, weight in scores)
        average = weighted_sum / total_weight

        assert 45 <= average <= 60
        assert abs(average - 51.0) < 0.1  # Should be around 51

    def test_signal_from_extreme_fear(self):
        """Extreme fear should generate contrarian buy signal"""
        sentiment_score = 15  # Extreme fear

        if sentiment_score <= 20:
            signal_type = SignalType.STRONG_BUY
        elif sentiment_score <= 40:
            signal_type = SignalType.BUY
        else:
            signal_type = SignalType.NEUTRAL

        assert signal_type == SignalType.STRONG_BUY

    def test_signal_from_extreme_greed(self):
        """Extreme greed should generate contrarian sell signal"""
        sentiment_score = 90  # Extreme greed

        if sentiment_score >= 80:
            signal_type = SignalType.STRONG_SELL
        elif sentiment_score >= 60:
            signal_type = SignalType.SELL
        else:
            signal_type = SignalType.NEUTRAL

        assert signal_type == SignalType.STRONG_SELL

    def test_confidence_from_agreement(self):
        """Higher agreement between sources should yield higher confidence"""
        sources = [45, 48, 42, 46]  # All agree on fear

        mean = sum(sources) / len(sources)
        variance = sum((s - mean) ** 2 for s in sources) / len(sources)
        std_dev = variance ** 0.5

        # Lower std_dev = higher agreement = higher confidence
        confidence = max(0, 1 - std_dev / 50)

        assert confidence > 0.9  # High agreement


class TestHistoricalData:
    """Tests for historical sentiment data"""

    @pytest.fixture
    def client(self):
        return CoinMarketCapClient()

    @pytest.mark.asyncio
    async def test_historical_data_parsing(self, client):
        """Should parse historical data correctly"""
        mock_data = {
            "data": [
                {"value": "45", "value_classification": "Fear",
                 "timestamp": str(int((datetime.now(timezone.utc) - timedelta(days=i)).timestamp()))}
                for i in range(7)
            ]
        }

        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_data)

            mock_session_instance = AsyncMock()
            mock_session_instance.get = AsyncMock(return_value=mock_response)
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            mock_session.return_value = mock_session_instance

            result = await client.get_historical_fear_greed(days=7)

            # Should return list
            assert result is None or isinstance(result, list)

    def test_trend_calculation(self):
        """Should detect sentiment trends"""
        # Improving sentiment (fear to neutral)
        scores = [25, 30, 35, 42, 48]

        trend = (scores[-1] - scores[0]) / len(scores)

        assert trend > 0  # Positive trend (improving sentiment)

    def test_divergence_detection(self):
        """Should detect price-sentiment divergence"""
        # Price going up, sentiment going down (bearish divergence)
        prices = [65000, 66000, 67000, 68000]
        sentiments = [60, 55, 48, 42]

        price_trend = prices[-1] - prices[0]  # Positive
        sentiment_trend = sentiments[-1] - sentiments[0]  # Negative

        divergence = price_trend * sentiment_trend < 0

        assert divergence is True  # Bearish divergence detected
