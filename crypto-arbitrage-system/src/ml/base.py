"""
Base Sentiment Analyzer

Abstract base class for sentiment analyzers.
"""

from abc import ABC, abstractmethod
from typing import List

from .models import SentimentResult


class BaseSentimentAnalyzer(ABC):
    """Abstract base for sentiment analyzers"""

    @abstractmethod
    async def analyze(self, text: str) -> SentimentResult:
        pass

    @abstractmethod
    async def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        pass
