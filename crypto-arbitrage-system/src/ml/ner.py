"""
Crypto Named Entity Recognition

Named Entity Recognition for crypto assets, exchanges, and people.
"""

import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

# Optional imports
try:
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


class CryptoNER:
    """
    Named Entity Recognition for crypto assets

    Identifies:
    - Cryptocurrency mentions (BTC, Bitcoin, ETH, etc.)
    - Exchange mentions
    - People (founders, influencers)
    - Organizations
    """

    # Common crypto name mappings
    CRYPTO_ALIASES = {
        "bitcoin": "BTC", "btc": "BTC",
        "ethereum": "ETH", "eth": "ETH", "ether": "ETH",
        "solana": "SOL", "sol": "SOL",
        "ripple": "XRP", "xrp": "XRP",
        "cardano": "ADA", "ada": "ADA",
        "polkadot": "DOT", "dot": "DOT",
        "dogecoin": "DOGE", "doge": "DOGE",
        "avalanche": "AVAX", "avax": "AVAX",
        "chainlink": "LINK", "link": "LINK",
        "polygon": "MATIC", "matic": "MATIC",
        "uniswap": "UNI", "uni": "UNI",
        "litecoin": "LTC", "ltc": "LTC",
        "usdt": "USDT", "tether": "USDT",
        "usdc": "USDC"
    }

    EXCHANGES = [
        "binance", "coinbase", "kraken", "kucoin", "mexc",
        "bybit", "okx", "bitfinex", "gemini", "ftx", "huobi"
    ]

    def __init__(self):
        self._ner_pipeline = None

    async def initialize(self):
        """Initialize NER model"""
        if TRANSFORMERS_AVAILABLE and self._ner_pipeline is None:
            try:
                self._ner_pipeline = pipeline(
                    "ner",
                    model="dslim/bert-base-NER",
                    aggregation_strategy="simple"
                )
            except Exception as e:
                logger.warning(f"Failed to load NER model: {e}")

    async def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract entities from text

        Returns:
            Dict with entity types and values
        """
        await self.initialize()

        entities = {
            "cryptocurrencies": [],
            "exchanges": [],
            "people": [],
            "organizations": []
        }

        text_lower = text.lower()

        # Extract crypto mentions
        for alias, symbol in self.CRYPTO_ALIASES.items():
            if alias in text_lower and symbol not in entities["cryptocurrencies"]:
                entities["cryptocurrencies"].append(symbol)

        # Look for $SYMBOL pattern
        symbols = re.findall(r'\$([A-Z]{2,10})', text.upper())
        for symbol in symbols:
            if symbol not in entities["cryptocurrencies"]:
                entities["cryptocurrencies"].append(symbol)

        # Extract exchange mentions
        for exchange in self.EXCHANGES:
            if exchange in text_lower:
                entities["exchanges"].append(exchange.title())

        # Use NER model for people and organizations
        if self._ner_pipeline:
            try:
                ner_results = self._ner_pipeline(text[:512])
                for entity in ner_results:
                    if entity["entity_group"] == "PER":
                        if entity["word"] not in entities["people"]:
                            entities["people"].append(entity["word"])
                    elif entity["entity_group"] == "ORG":
                        if entity["word"] not in entities["organizations"]:
                            entities["organizations"].append(entity["word"])
            except Exception as e:
                logger.warning(f"NER extraction error: {e}")

        return entities
