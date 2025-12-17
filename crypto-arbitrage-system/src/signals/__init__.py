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

Module Structure:
- enums.py: SentimentLevel, SignalType, NewsCategory
- models.py: SentimentDataPoint, NewsItem, TradingSignal
- clients.py: CoinMarketCapClient, CryptoCompareClient
- aggregator.py: SentimentAggregator
- generator.py: SignalGenerator
- service.py: SignalService
"""

from pathlib import Path
from typing import Callable

# Import from submodules for backward compatibility
from .enums import SentimentLevel, SignalType, NewsCategory
from .models import SentimentDataPoint, NewsItem, TradingSignal
from .clients import CoinMarketCapClient, CryptoCompareClient
from .aggregator import SentimentAggregator
from .generator import SignalGenerator
from .service import SignalService, create_signal_service


__all__ = [
    # Enums
    "SentimentLevel",
    "SignalType",
    "NewsCategory",

    # Models
    "SentimentDataPoint",
    "NewsItem",
    "TradingSignal",

    # Clients
    "CoinMarketCapClient",
    "CryptoCompareClient",

    # Core classes
    "SentimentAggregator",
    "SignalGenerator",
    "SignalService",

    # Factory
    "create_signal_service",
]
