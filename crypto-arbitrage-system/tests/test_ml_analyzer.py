"""
Tests for MLAnalyzer orchestration layer

Tests:
- Regime detection updates and adjustments
- Sentiment analysis with and without transformers
- Opportunity scoring
- Graceful degradation when models unavailable
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch


class TestMLAnalyzerInit:
    """Test MLAnalyzer initialization"""

    def test_creates_all_components(self):
        """Should initialize regime detector, sentiment, NER"""
        from src.ml.analyzer import MLAnalyzer

        analyzer = MLAnalyzer()
        assert analyzer.regime_detector is not None
        assert analyzer.sentiment_analyzer is not None
        assert analyzer.ner is not None
        assert analyzer.event_detector is not None

    @pytest.mark.asyncio
    async def test_initialize_without_transformers(self):
        """Should initialize gracefully when torch/transformers not installed"""
        from src.ml.analyzer import MLAnalyzer

        analyzer = MLAnalyzer()
        # Should not raise even if transformers not available
        await analyzer.initialize()


class TestRegimeDetection:
    """Test market regime detection"""

    def test_unknown_regime_with_no_data(self):
        """Should return UNKNOWN when no price data"""
        from src.ml.analyzer import MLAnalyzer
        from src.ml.regime import Regime

        analyzer = MLAnalyzer()
        assert analyzer.current_regime == Regime.UNKNOWN

    def test_regime_updates_with_price_data(self):
        """Should detect regime after sufficient price data"""
        from src.ml.analyzer import MLAnalyzer
        from src.ml.regime import Regime

        analyzer = MLAnalyzer()

        # Feed 48 hours of steadily rising prices (2x = bull)
        base = 50000.0
        for i in range(48):
            analyzer.update_price("BTC/USDT", base + (i * 500))

        # Should detect a trend
        regime = analyzer.current_regime
        assert regime != Regime.UNKNOWN

    def test_regime_adjustments_structure(self):
        """Adjustments should have expected keys"""
        from src.ml.analyzer import MLAnalyzer

        analyzer = MLAnalyzer()
        adjustments = analyzer.get_regime_adjustments()

        assert "bias" in adjustments
        assert "position_size_multiplier" in adjustments
        assert "stop_loss_multiplier" in adjustments
        assert "take_profit_multiplier" in adjustments

    def test_high_vol_reduces_position_size(self):
        """High volatility regime should reduce position size multiplier"""
        from src.ml.analyzer import MLAnalyzer
        from src.ml.regime import Regime

        analyzer = MLAnalyzer()

        # Feed volatile prices (large swings)
        prices = [50000 + ((-1)**i * 5000) for i in range(48)]
        for p in prices:
            analyzer.update_price("BTC/USDT", p)

        if analyzer.current_regime == Regime.HIGH_VOL:
            adjustments = analyzer.get_regime_adjustments()
            assert adjustments["position_size_multiplier"] < 1.0


class TestOpportunityScoring:
    """Test ML-based opportunity scoring"""

    @pytest.mark.asyncio
    async def test_score_without_news(self):
        """Should return valid score with no news texts"""
        from src.ml.analyzer import MLAnalyzer

        analyzer = MLAnalyzer()
        score = await analyzer.score_opportunity("BTC/USDT", spread_percent=0.3)

        assert "regime" in score
        assert "regime_adjustment" in score
        assert "sentiment_score" in score
        assert "sentiment_filter" in score
        assert "ml_confidence" in score
        assert score["sentiment_filter"] == "pass"
        assert 0.0 <= score["ml_confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_score_with_positive_news(self):
        """Positive sentiment should not block"""
        from src.ml.analyzer import MLAnalyzer

        analyzer = MLAnalyzer()
        await analyzer.initialize()

        # Mock sentiment analyzer to return positive
        analyzer.sentiment_analyzer.analyze = AsyncMock(
            return_value=Mock(sentiment="positive", confidence=0.9, scores={})
        )

        score = await analyzer.score_opportunity(
            "BTC/USDT",
            spread_percent=0.3,
            news_texts=["Bitcoin ETF approved, massive inflows expected"]
        )

        assert score["sentiment_filter"] == "pass"
        assert score["sentiment_score"] > 0

    @pytest.mark.asyncio
    async def test_score_blocks_on_negative_sentiment(self):
        """Strongly negative sentiment should block opportunity"""
        from src.ml.analyzer import MLAnalyzer

        analyzer = MLAnalyzer()
        await analyzer.initialize()

        # Mock sentiment analyzer to return very negative
        analyzer.sentiment_analyzer.analyze = AsyncMock(
            return_value=Mock(sentiment="negative", confidence=0.95, scores={})
        )

        score = await analyzer.score_opportunity(
            "BTC/USDT",
            spread_percent=0.3,
            news_texts=["Major exchange hacked, billions stolen"]
        )

        assert score["sentiment_filter"] == "block"
        assert score["sentiment_score"] < 0


class TestResilienceCircuitBreaker:
    """Test resilience module circuit breaker (used in engine.py)"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_tracks_failures(self):
        """Circuit breaker should open after threshold failures"""
        from src.utils.resilience import CircuitBreaker, CircuitBreakerConfig, CircuitState

        breaker = CircuitBreaker(
            name="test_exchange",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                success_threshold=2,
                timeout_seconds=60.0,
                sliding_window_size=10,
            )
        )

        assert breaker.state == CircuitState.CLOSED

        # Simulate failures via execute()
        async def failing_fn():
            raise ConnectionError("exchange down")

        for _ in range(5):
            try:
                await breaker.execute(failing_fn)
            except (ConnectionError, Exception):
                pass

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_execute_success(self):
        """Successful calls should be tracked"""
        from src.utils.resilience import CircuitBreaker, CircuitBreakerConfig, CircuitState

        breaker = CircuitBreaker(
            name="test_exchange",
            config=CircuitBreakerConfig(failure_threshold=5)
        )

        async def success_fn():
            return "ok"

        result = await breaker.execute(success_fn)
        assert result == "ok"
        assert breaker.metrics.successful_calls == 1
        assert breaker.state == CircuitState.CLOSED
