"""
Signal Models

Dataclasses for sentiment data, news items, and trading signals.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from .enums import NewsCategory, SignalType


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
