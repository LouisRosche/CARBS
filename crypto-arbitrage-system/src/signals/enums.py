"""
Signal Enums

Enumerations for sentiment levels, signal types, and news categories.
"""

from enum import Enum


class SentimentLevel(Enum):
    """Sentiment classification"""
    EXTREME_FEAR = "extreme_fear"      # 0-20
    FEAR = "fear"                       # 21-40
    NEUTRAL = "neutral"                 # 41-60
    GREED = "greed"                     # 61-80
    EXTREME_GREED = "extreme_greed"    # 81-100


class SignalType(Enum):
    """Trading signal types"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class NewsCategory(Enum):
    """News categorization"""
    REGULATORY = "regulatory"
    ADOPTION = "adoption"
    TECHNOLOGY = "technology"
    MARKET = "market"
    SECURITY = "security"  # Hacks, exploits
    MACRO = "macro"        # Fed, inflation, etc.
    WHALE = "whale"        # Large movements
    UNKNOWN = "unknown"
