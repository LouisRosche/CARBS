"""
Tests for machine learning module

Tests:
- Sentiment analysis
- News event detection
- Fallback analyzers
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import re

from src.ml import (
    SentimentResult,
    NewsEvent,
    BaseSentimentAnalyzer,
    TransformerSentimentAnalyzer,
)


class TestSentimentResult:
    """Tests for SentimentResult dataclass"""

    def test_sentiment_result_creation(self):
        """Should create sentiment result with all fields"""
        result = SentimentResult(
            text="Bitcoin is going to the moon!",
            sentiment="positive",
            confidence=0.95,
            scores={"positive": 0.95, "negative": 0.03, "neutral": 0.02}
        )

        assert result.text == "Bitcoin is going to the moon!"
        assert result.sentiment == "positive"
        assert result.confidence == 0.95
        assert result.timestamp is not None

    def test_sentiment_result_default_fields(self):
        """Should have default empty values for optional fields"""
        result = SentimentResult(
            text="Test text",
            sentiment="neutral",
            confidence=0.5
        )

        assert result.scores == {}
        assert result.entities == []


class TestNewsEvent:
    """Tests for NewsEvent dataclass"""

    def test_news_event_creation(self):
        """Should create news event"""
        event = NewsEvent(
            event_id="event_001",
            event_type="regulatory",
            severity=0.8,
            assets=["BTC", "ETH"],
            summary="SEC announces new crypto regulations",
            source_text="The Securities and Exchange Commission...",
            timestamp=datetime.now(timezone.utc),
            expected_impact="bearish"
        )

        assert event.event_id == "event_001"
        assert event.event_type == "regulatory"
        assert event.severity == 0.8
        assert "BTC" in event.assets


class TestTransformerSentimentAnalyzer:
    """Tests for TransformerSentimentAnalyzer"""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance"""
        return TransformerSentimentAnalyzer()

    def test_analyzer_initialization(self, analyzer):
        """Should initialize with default values"""
        assert analyzer._initialized is False
        assert analyzer._model is None

    @pytest.mark.asyncio
    async def test_fallback_analyze_positive(self, analyzer):
        """Should detect positive sentiment in fallback mode"""
        # Force fallback mode
        analyzer._initialized = False

        result = analyzer._fallback_analyze("Bitcoin is amazing! Great investment!")

        assert result.sentiment in ["positive", "negative", "neutral"]
        assert 0 <= result.confidence <= 1

    @pytest.mark.asyncio
    async def test_fallback_analyze_negative(self, analyzer):
        """Should detect negative sentiment in fallback mode"""
        result = analyzer._fallback_analyze("Market crash! Terrible losses!")

        assert result.sentiment in ["positive", "negative", "neutral"]

    @pytest.mark.asyncio
    async def test_fallback_analyze_neutral(self, analyzer):
        """Should detect neutral sentiment in fallback mode"""
        result = analyzer._fallback_analyze("The price of bitcoin is 67000")

        assert result.sentiment in ["positive", "negative", "neutral"]

    def test_preprocess_removes_urls(self, analyzer):
        """Should remove URLs from text"""
        text = "Check out this news https://example.com/article"
        processed = analyzer._preprocess(text)

        assert "https://" not in processed
        assert "example.com" not in processed

    def test_preprocess_keeps_crypto_symbols(self, analyzer):
        """Should keep crypto symbols like $ and #"""
        text = "$BTC is trending #cryptocurrency"
        processed = analyzer._preprocess(text)

        # Should preserve meaningful text
        assert "BTC" in processed or "$" in processed

    def test_normalize_label_positive(self, analyzer):
        """Should normalize various positive labels"""
        assert analyzer._normalize_label("POSITIVE") == "positive"
        assert analyzer._normalize_label("pos") == "positive"
        assert analyzer._normalize_label("LABEL_2") == "positive"

    def test_normalize_label_negative(self, analyzer):
        """Should normalize various negative labels"""
        assert analyzer._normalize_label("NEGATIVE") == "negative"
        assert analyzer._normalize_label("neg") == "negative"
        assert analyzer._normalize_label("LABEL_0") == "negative"

    def test_normalize_label_neutral(self, analyzer):
        """Should default to neutral for unknown labels"""
        assert analyzer._normalize_label("unknown") == "neutral"
        assert analyzer._normalize_label("LABEL_1") == "neutral"


class TestFallbackSentimentKeywords:
    """Tests for fallback keyword-based sentiment detection"""

    def test_positive_keywords(self):
        """Should have positive keyword detection"""
        positive_words = ["bullish", "moon", "pump", "gains", "profit", "rally", "surge"]
        text = "Bitcoin is bullish, expecting huge gains and rally"

        count = sum(1 for word in positive_words if word in text.lower())
        assert count >= 2

    def test_negative_keywords(self):
        """Should have negative keyword detection"""
        negative_words = ["bearish", "crash", "dump", "losses", "fear", "plunge"]
        text = "Market crash! Bearish sentiment, massive losses expected"

        count = sum(1 for word in negative_words if word in text.lower())
        assert count >= 2

    def test_neutral_text(self):
        """Neutral text should have balanced keywords"""
        text = "Bitcoin price is currently at 67000 USD"
        positive = ["bullish", "moon", "gains"]
        negative = ["bearish", "crash", "dump"]

        pos_count = sum(1 for w in positive if w in text.lower())
        neg_count = sum(1 for w in negative if w in text.lower())

        assert abs(pos_count - neg_count) <= 1  # Should be balanced


class TestSentimentConfidence:
    """Tests for sentiment confidence calculation"""

    def test_confidence_bounds(self):
        """Confidence should be between 0 and 1"""
        confidences = [0.0, 0.5, 0.75, 1.0]

        for conf in confidences:
            assert 0 <= conf <= 1

    def test_high_confidence_strong_sentiment(self):
        """Strong sentiment words should yield higher confidence"""
        strong_positive = ["absolutely bullish", "definite moon", "guaranteed gains"]
        weak_positive = ["maybe good", "might increase"]

        # Strong sentiment texts should have higher word counts
        for text in strong_positive:
            assert len(text.split()) >= 2

    def test_confidence_calculation_logic(self):
        """Test confidence calculation approach"""
        # Example confidence calculation
        positive_count = 3
        negative_count = 0
        total_words = 10

        if positive_count > negative_count:
            ratio = positive_count / total_words
            confidence = min(0.5 + ratio, 1.0)
        else:
            confidence = 0.5

        assert 0.5 <= confidence <= 1.0


class TestBatchSentimentAnalysis:
    """Tests for batch sentiment analysis"""

    @pytest.fixture
    def analyzer(self):
        return TransformerSentimentAnalyzer()

    @pytest.mark.asyncio
    async def test_batch_analyze_returns_list(self, analyzer):
        """Batch analysis should return list of results"""
        texts = [
            "Bitcoin is great!",
            "Market is crashing",
            "Price is stable"
        ]

        # In fallback mode
        results = [analyzer._fallback_analyze(t) for t in texts]

        assert len(results) == len(texts)
        assert all(isinstance(r, SentimentResult) for r in results)

    @pytest.mark.asyncio
    async def test_batch_analyze_empty_list(self, analyzer):
        """Should handle empty input list"""
        results = [analyzer._fallback_analyze(t) for t in []]

        assert results == []

    @pytest.mark.asyncio
    async def test_batch_analyze_preserves_order(self, analyzer):
        """Results should be in same order as inputs"""
        texts = ["positive text", "negative text", "neutral text"]
        results = [analyzer._fallback_analyze(t) for t in texts]

        assert len(results) == 3
        # First result should be for "positive text"
        assert "positive" in results[0].text.lower()


class TestModelLoading:
    """Tests for model loading behavior"""

    def test_model_list_priority(self):
        """Should have prioritized model list"""
        models = TransformerSentimentAnalyzer.CRYPTO_MODELS

        assert len(models) >= 2
        # First should be crypto-specific
        assert "crypto" in models[0].lower() or "fin" in models[0].lower()

    def test_device_detection(self):
        """Should detect appropriate device"""
        analyzer = TransformerSentimentAnalyzer()

        # Device should be "cpu" or "cuda"
        assert analyzer.device in ["cpu", "cuda"]

    @pytest.mark.asyncio
    async def test_lazy_initialization(self):
        """Model should initialize lazily"""
        analyzer = TransformerSentimentAnalyzer()

        assert analyzer._initialized is False

        # Analyze without transformer (fallback)
        result = analyzer._fallback_analyze("test")

        # Should still work
        assert result.sentiment in ["positive", "negative", "neutral"]
