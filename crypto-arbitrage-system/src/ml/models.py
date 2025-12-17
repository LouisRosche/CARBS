"""
ML Models

Dataclasses for ML results.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List


@dataclass
class SentimentResult:
    """Result of sentiment analysis"""
    text: str
    sentiment: str  # positive, negative, neutral
    confidence: float
    scores: Dict[str, float] = field(default_factory=dict)
    entities: List[Dict] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class NewsEvent:
    """Detected news event"""
    event_id: str
    event_type: str  # regulatory, hack, partnership, listing, etc.
    severity: float  # 0-1
    assets: List[str]
    summary: str
    source_text: str
    timestamp: datetime
    expected_impact: str  # bullish, bearish, neutral
