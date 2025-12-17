"""
Transformer Sentiment Analyzer

Transformer-based sentiment analysis with crypto-specific models.
"""

import logging
import re
from typing import List

from .base import BaseSentimentAnalyzer
from .models import SentimentResult

logger = logging.getLogger(__name__)

# Optional imports - gracefully handle missing dependencies
try:
    import torch
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("Transformers not installed. Using fallback sentiment analysis.")


class TransformerSentimentAnalyzer(BaseSentimentAnalyzer):
    """
    Transformer-based sentiment analysis

    Uses fine-tuned models for crypto-specific sentiment.
    Falls back to general financial models if unavailable.
    """

    # Model options (in order of preference)
    CRYPTO_MODELS = [
        "ElKulako/cryptobert",  # Crypto-specific BERT
        "ProsusAI/finbert",     # Financial BERT
        "cardiffnlp/twitter-roberta-base-sentiment-latest",  # Social media
        "distilbert-base-uncased-finetuned-sst-2-english"   # General fallback
    ]

    def __init__(self, model_name: str = None, device: str = None):
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu") if TRANSFORMERS_AVAILABLE else "cpu"

        self._model = None
        self._tokenizer = None
        self._pipeline = None
        self._initialized = False

    async def initialize(self):
        """Lazy initialization of model"""
        if self._initialized or not TRANSFORMERS_AVAILABLE:
            return

        # Try models in order of preference
        models_to_try = [self.model_name] if self.model_name else self.CRYPTO_MODELS

        for model_name in models_to_try:
            try:
                logger.info(f"Loading sentiment model: {model_name}")
                self._pipeline = pipeline(
                    "sentiment-analysis",
                    model=model_name,
                    device=0 if self.device == "cuda" else -1,
                    truncation=True,
                    max_length=512
                )
                self.model_name = model_name
                self._initialized = True
                logger.info(f"Successfully loaded: {model_name}")
                return
            except Exception as e:
                logger.warning(f"Failed to load {model_name}: {e}")

        logger.error("No sentiment models could be loaded")

    async def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment of text"""
        await self.initialize()

        if not self._initialized:
            return self._fallback_analyze(text)

        try:
            # Clean and truncate text
            text = self._preprocess(text)

            result = self._pipeline(text)[0]

            # Normalize labels across different models
            label = result["label"].lower()
            if label in ["positive", "pos", "label_2", "1"]:
                sentiment = "positive"
            elif label in ["negative", "neg", "label_0", "0"]:
                sentiment = "negative"
            else:
                sentiment = "neutral"

            return SentimentResult(
                text=text[:200],
                sentiment=sentiment,
                confidence=result["score"],
                scores={sentiment: result["score"]}
            )

        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return self._fallback_analyze(text)

    async def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """Analyze multiple texts"""
        await self.initialize()

        if not self._initialized:
            return [self._fallback_analyze(t) for t in texts]

        try:
            processed = [self._preprocess(t) for t in texts]
            results = self._pipeline(processed)

            return [
                SentimentResult(
                    text=texts[i][:200],
                    sentiment=self._normalize_label(r["label"]),
                    confidence=r["score"],
                    scores={self._normalize_label(r["label"]): r["score"]}
                )
                for i, r in enumerate(results)
            ]

        except Exception as e:
            logger.error(f"Batch sentiment analysis error: {e}")
            return [self._fallback_analyze(t) for t in texts]

    def _preprocess(self, text: str) -> str:
        """Preprocess text for analysis"""
        # Remove URLs
        text = re.sub(r'http\S+', '', text)
        # Remove special characters but keep crypto symbols
        text = re.sub(r'[^\w\s$#@]', ' ', text)
        # Normalize whitespace
        text = ' '.join(text.split())
        return text[:1000]  # Truncate very long texts

    def _normalize_label(self, label: str) -> str:
        """Normalize sentiment label"""
        label = label.lower()
        if label in ["positive", "pos", "label_2", "1", "bullish"]:
            return "positive"
        elif label in ["negative", "neg", "label_0", "0", "bearish"]:
            return "negative"
        return "neutral"

    def _fallback_analyze(self, text: str) -> SentimentResult:
        """Simple keyword-based fallback"""
        text_lower = text.lower()

        positive_words = [
            "bullish", "moon", "pump", "surge", "rally", "breakout",
            "adoption", "partnership", "growth", "profit", "gains",
            "upgrade", "launch", "success", "milestone", "record"
        ]

        negative_words = [
            "bearish", "crash", "dump", "plunge", "decline", "selloff",
            "hack", "exploit", "scam", "fraud", "lawsuit", "ban",
            "regulation", "fear", "loss", "fail", "warning"
        ]

        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)

        total = pos_count + neg_count
        if total == 0:
            return SentimentResult(
                text=text[:200],
                sentiment="neutral",
                confidence=0.5,
                scores={"neutral": 0.5}
            )

        pos_ratio = pos_count / total
        neg_ratio = neg_count / total

        if pos_ratio > 0.6:
            return SentimentResult(
                text=text[:200],
                sentiment="positive",
                confidence=pos_ratio,
                scores={"positive": pos_ratio, "negative": neg_ratio}
            )
        elif neg_ratio > 0.6:
            return SentimentResult(
                text=text[:200],
                sentiment="negative",
                confidence=neg_ratio,
                scores={"positive": pos_ratio, "negative": neg_ratio}
            )
        else:
            return SentimentResult(
                text=text[:200],
                sentiment="neutral",
                confidence=0.5,
                scores={"positive": pos_ratio, "negative": neg_ratio, "neutral": 0.5}
            )
