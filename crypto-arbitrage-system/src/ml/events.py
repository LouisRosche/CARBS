"""
News Event Detector

Detects significant events from news text.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional

from .base import BaseSentimentAnalyzer
from .models import NewsEvent
from .sentiment import TransformerSentimentAnalyzer
from .ner import CryptoNER

logger = logging.getLogger(__name__)


class NewsEventDetector:
    """
    Detects significant events from news

    Event types:
    - regulatory: Government actions, legal decisions
    - security: Hacks, exploits, vulnerabilities
    - adoption: New partnerships, integrations
    - listing: Exchange listings/delistings
    - technical: Network upgrades, forks
    - whale: Large transactions
    - macro: Fed decisions, economic events
    """

    EVENT_PATTERNS = {
        "regulatory": [
            r"sec\s+(approved|rejected|sued|charges)",
            r"(ban|restrict|regulate)\s+(crypto|bitcoin|trading)",
            r"(lawsuit|legal action|court)\s+.*(crypto|bitcoin|exchange)",
            r"(compliance|regulation|regulatory)\s+(framework|requirement)"
        ],
        "security": [
            r"(hack|hacked|exploit|breach|stolen)",
            r"(vulnerability|bug|flaw)\s+(found|discovered|exploited)",
            r"\$\d+\s*(million|billion)?\s*(stolen|lost|hacked)",
            r"(rug pull|exit scam|ponzi)"
        ],
        "adoption": [
            r"(partnership|partners with|collaborat)",
            r"(accept|accepting|payment)\s+.*(bitcoin|crypto|btc)",
            r"(institutional|corporate)\s+(investment|adoption|buying)",
            r"(etf|fund)\s+(approved|launched|filing)"
        ],
        "listing": [
            r"(list|listing|listed)\s+(on|by)\s+\w+",
            r"(delist|delisting|removed)\s+.*(exchange|binance|coinbase)",
            r"(new trading pair|trading opens)"
        ],
        "technical": [
            r"(upgrade|fork|hardfork|softfork)",
            r"(mainnet|testnet)\s+(launch|live|upgrade)",
            r"(protocol|network)\s+(update|improvement|upgrade)"
        ],
        "whale": [
            r"(whale|large)\s+(transfer|transaction|movement)",
            r"\d+\s*(btc|bitcoin|eth)\s+(moved|transferred)",
            r"(dormant|inactive)\s+(wallet|address)\s+(activated|moved)"
        ],
        "macro": [
            r"(fed|federal reserve)\s+(rate|decision|meeting)",
            r"(inflation|cpi|employment)\s+(data|report|number)",
            r"(recession|economic|gdp)\s+(fear|concern|data)"
        ]
    }

    IMPACT_KEYWORDS = {
        "bullish": [
            "approved", "adoption", "partnership", "launch", "upgrade",
            "institutional", "etf approved", "record high", "breakout"
        ],
        "bearish": [
            "hack", "exploit", "ban", "lawsuit", "crash", "delisting",
            "scam", "fraud", "rejected", "investigation", "stolen"
        ]
    }

    def __init__(self, sentiment_analyzer: BaseSentimentAnalyzer = None):
        self.sentiment_analyzer = sentiment_analyzer or TransformerSentimentAnalyzer()
        self.ner = CryptoNER()

    async def detect_events(self, texts: List[str]) -> List[NewsEvent]:
        """Detect events from list of news texts"""
        events = []

        for text in texts:
            event = await self._analyze_text(text)
            if event:
                events.append(event)

        return events

    async def _analyze_text(self, text: str) -> Optional[NewsEvent]:
        """Analyze single text for events"""
        text_lower = text.lower()

        # Check for event patterns
        detected_type = None
        max_matches = 0

        for event_type, patterns in self.EVENT_PATTERNS.items():
            matches = sum(1 for p in patterns if re.search(p, text_lower))
            if matches > max_matches:
                max_matches = matches
                detected_type = event_type

        if not detected_type or max_matches == 0:
            return None

        # Extract entities
        entities = await self.ner.extract_entities(text)
        assets = entities.get("cryptocurrencies", ["MARKET"])

        # Determine impact
        impact = "neutral"
        for keyword in self.IMPACT_KEYWORDS["bullish"]:
            if keyword in text_lower:
                impact = "bullish"
                break
        for keyword in self.IMPACT_KEYWORDS["bearish"]:
            if keyword in text_lower:
                impact = "bearish"
                break

        # Calculate severity
        severity = min(1.0, max_matches / 3)  # More matches = higher severity

        # Get sentiment
        sentiment = await self.sentiment_analyzer.analyze(text)
        if sentiment.sentiment == "negative":
            severity = min(1.0, severity * 1.3)  # Boost for negative sentiment

        return NewsEvent(
            event_id=hashlib.sha256(text[:100].encode()).hexdigest()[:12],
            event_type=detected_type,
            severity=severity,
            assets=assets if assets else ["MARKET"],
            summary=text[:200],
            source_text=text,
            timestamp=datetime.now(timezone.utc),
            expected_impact=impact
        )
