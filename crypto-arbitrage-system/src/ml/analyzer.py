"""
ML Analyzer - Unified ML Pipeline Orchestrator

Provides a single interface for the trading engine to access:
- Market regime detection (adjusts position sizing)
- Sentiment analysis (filters opportunities during high-fear periods)
- Named entity recognition (tracks asset mentions)
- News event detection (identifies market-moving events)

Usage:
    analyzer = MLAnalyzer()
    await analyzer.initialize()

    # Update with price data
    analyzer.update_price("BTC/USDT", 67500.0)

    # Get regime-based adjustments
    adjustments = analyzer.get_regime_adjustments()

    # Score opportunity with ML signals
    ml_score = await analyzer.score_opportunity("BTC/USDT", spread_percent=0.3)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .regime import RegimeDetector, Regime
from .sentiment import TransformerSentimentAnalyzer, TRANSFORMERS_AVAILABLE
from .ner import CryptoNER
from .events import NewsEventDetector
from .models import SentimentResult, NewsEvent

logger = logging.getLogger(__name__)


class MLAnalyzer:
    """
    Unified ML pipeline orchestrator.

    Coordinates regime detection, sentiment analysis, and entity recognition
    to provide trading signals to the arbitrage engine.
    """

    def __init__(self, lookback_days: int = 30):
        self.regime_detector = RegimeDetector(lookback_days=lookback_days)
        self.sentiment_analyzer = TransformerSentimentAnalyzer()
        self.ner = CryptoNER()
        self.event_detector = NewsEventDetector(self.sentiment_analyzer)

        self._initialized = False
        self._latest_sentiment: Dict[str, SentimentResult] = {}
        self._latest_events: List[NewsEvent] = []

        logger.info("MLAnalyzer created (call initialize() to load models)")

    async def initialize(self) -> None:
        """Initialize all ML models. Call once at startup."""
        if self._initialized:
            return

        if not TRANSFORMERS_AVAILABLE:
            logger.warning(
                "ML dependencies (torch, transformers) not installed. "
                "ML features will use fallback methods. "
                "Install with: pip install torch transformers"
            )
            self._initialized = True
            return

        try:
            await self.sentiment_analyzer.initialize()
            await self.ner.initialize()
            self._initialized = True
            logger.info("MLAnalyzer initialized successfully")
        except Exception as e:
            logger.warning(f"MLAnalyzer partial initialization: {e}")
            # Continue even if some models fail — regime detector doesn't need initialization

    def update_price(self, symbol: str, price: float, timestamp: datetime = None) -> None:
        """Feed price data to regime detector."""
        self.regime_detector.update(price, timestamp)

    @property
    def current_regime(self) -> Regime:
        """Get current market regime."""
        return self.regime_detector.current_regime

    def get_regime_adjustments(self) -> Dict:
        """
        Get strategy adjustments for current market regime.

        Returns dict with:
            - bias: "long", "short", or "neutral"
            - position_size_multiplier: float (e.g., 0.5 for high vol)
            - stop_loss_multiplier: float
            - take_profit_multiplier: float
        """
        return self.regime_detector.get_strategy_adjustment()

    async def analyze_sentiment(self, text: str) -> Optional[SentimentResult]:
        """
        Analyze sentiment of a text string.

        Returns SentimentResult or None if analysis fails.
        """
        try:
            result = await self.sentiment_analyzer.analyze(text)
            return result
        except Exception as e:
            logger.warning(f"Sentiment analysis failed: {e}")
            return None

    async def analyze_news_batch(self, texts: List[str]) -> List[SentimentResult]:
        """Analyze sentiment for multiple texts."""
        results = []
        for text in texts:
            result = await self.analyze_sentiment(text)
            if result:
                results.append(result)
        return results

    async def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract crypto entities from text."""
        try:
            return await self.ner.extract_entities(text)
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            return {"cryptocurrencies": [], "exchanges": [], "people": []}

    async def score_opportunity(
        self,
        symbol: str,
        spread_percent: float = 0.0,
        news_texts: List[str] = None,
    ) -> Dict:
        """
        Score an arbitrage opportunity using ML signals.

        Returns dict with:
            - regime: current market regime
            - regime_adjustment: position size multiplier from regime
            - sentiment_score: average sentiment (-1 to 1), 0 if no news
            - sentiment_filter: "pass" or "block" (blocks on strong negative sentiment)
            - ml_confidence: overall ML confidence (0-1)
        """
        adjustments = self.get_regime_adjustments()

        # Sentiment scoring from recent news (if provided)
        sentiment_score = 0.0
        sentiment_filter = "pass"

        if news_texts:
            sentiments = await self.analyze_news_batch(news_texts)
            if sentiments:
                scores = []
                for s in sentiments:
                    if s.sentiment == "positive":
                        scores.append(s.confidence)
                    elif s.sentiment == "negative":
                        scores.append(-s.confidence)
                    else:
                        scores.append(0.0)
                sentiment_score = sum(scores) / len(scores)

                # Block on strongly negative sentiment
                if sentiment_score < -0.6:
                    sentiment_filter = "block"
                    logger.info(
                        f"ML sentiment filter blocking {symbol}: "
                        f"score={sentiment_score:.2f}"
                    )

        # Overall ML confidence based on regime clarity and data availability
        regime = self.current_regime
        regime_confidence = 0.8 if regime != Regime.UNKNOWN else 0.3

        ml_confidence = regime_confidence
        if news_texts and sentiment_score != 0.0:
            # Blend regime and sentiment confidence
            ml_confidence = (regime_confidence + abs(sentiment_score)) / 2

        return {
            "regime": regime.value,
            "regime_adjustment": adjustments.get("position_size_multiplier", 1.0),
            "sentiment_score": sentiment_score,
            "sentiment_filter": sentiment_filter,
            "ml_confidence": min(ml_confidence, 1.0),
        }
