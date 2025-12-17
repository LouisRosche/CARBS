"""
Machine Learning Module

Advanced ML capabilities:
- Transformer-based sentiment analysis
- Named Entity Recognition for crypto assets
- News classification and event detection
- Self-learning strategy optimization
- Regime detection
- Research paper ingestion

Module Structure:
- models.py: SentimentResult, NewsEvent
- base.py: BaseSentimentAnalyzer
- sentiment.py: TransformerSentimentAnalyzer
- ner.py: CryptoNER
- events.py: NewsEventDetector
- learner.py: StrategyLearner
- regime.py: RegimeDetector, Regime
- research.py: ResearchIngester
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Check for transformers availability
try:
    import torch
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("Transformers not installed. Using fallback sentiment analysis.")

# Import from submodules for backward compatibility
from .models import SentimentResult, NewsEvent
from .base import BaseSentimentAnalyzer
from .sentiment import TransformerSentimentAnalyzer
from .ner import CryptoNER
from .events import NewsEventDetector
from .learner import StrategyLearner
from .regime import RegimeDetector, Regime
from .research import ResearchIngester


def create_sentiment_analyzer() -> BaseSentimentAnalyzer:
    """Create sentiment analyzer with best available model"""
    return TransformerSentimentAnalyzer()


def create_ml_pipeline(data_dir: Path = None) -> dict:
    """Create complete ML pipeline"""
    data_dir = data_dir or Path("data/ml")

    sentiment = TransformerSentimentAnalyzer()
    ner = CryptoNER()
    events = NewsEventDetector(sentiment)
    learner = StrategyLearner(data_dir / "learning")
    regime = RegimeDetector()
    research = ResearchIngester(data_dir / "research")

    return {
        "sentiment": sentiment,
        "ner": ner,
        "events": events,
        "learner": learner,
        "regime": regime,
        "research": research
    }


__all__ = [
    # Models
    "SentimentResult",
    "NewsEvent",

    # Base
    "BaseSentimentAnalyzer",

    # Analyzers
    "TransformerSentimentAnalyzer",
    "CryptoNER",
    "NewsEventDetector",

    # Learning
    "StrategyLearner",
    "RegimeDetector",
    "Regime",
    "ResearchIngester",

    # Factory functions
    "create_sentiment_analyzer",
    "create_ml_pipeline",

    # Flags
    "TRANSFORMERS_AVAILABLE",
]
