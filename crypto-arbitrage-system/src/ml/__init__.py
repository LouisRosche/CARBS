"""
Machine Learning Module

Advanced ML capabilities:
- Transformer-based sentiment analysis
- Named Entity Recognition for crypto assets
- News classification and event detection
- Self-learning strategy optimization
- Regime detection
- Research paper ingestion
"""

import asyncio
import logging
import hashlib
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from pathlib import Path
from collections import deque
from abc import ABC, abstractmethod
import json
import re

logger = logging.getLogger(__name__)

# Optional imports - gracefully handle missing dependencies
try:
    import torch
    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        AutoModelForTokenClassification,
        pipeline
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("Transformers not installed. Using fallback sentiment analysis.")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


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


class BaseSentimentAnalyzer(ABC):
    """Abstract base for sentiment analyzers"""

    @abstractmethod
    async def analyze(self, text: str) -> SentimentResult:
        pass

    @abstractmethod
    async def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        pass


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


class StrategyLearner:
    """
    Self-learning strategy optimization

    Features:
    - Tracks strategy performance over time
    - Automatically adjusts parameters
    - Detects regime changes
    - A/B tests strategy variations
    """

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data/ml/learning")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Performance tracking
        self._performance_history: Dict[str, deque] = {}
        self._parameter_history: Dict[str, List] = {}

        # Current best parameters
        self._best_params: Dict[str, Dict] = {}

        # Learning settings
        self.learning_rate = 0.1
        self.exploration_rate = 0.2
        self.min_samples = 20

        self._load_state()

    def _load_state(self):
        """Load learning state"""
        state_file = self.data_dir / "learner_state.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    data = json.load(f)
                    self._best_params = data.get("best_params", {})
            except Exception as e:
                logger.error(f"Failed to load learner state: {e}")

    def _save_state(self):
        """Save learning state"""
        state_file = self.data_dir / "learner_state.json"
        with open(state_file, 'w') as f:
            json.dump({"best_params": self._best_params}, f, indent=2)

    def record_trade(
        self,
        strategy_name: str,
        parameters: Dict,
        result: Dict  # pnl, win, etc.
    ):
        """Record trade result for learning"""
        if strategy_name not in self._performance_history:
            self._performance_history[strategy_name] = deque(maxlen=1000)
            self._parameter_history[strategy_name] = []

        self._performance_history[strategy_name].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "parameters": parameters,
            "result": result
        })

        self._parameter_history[strategy_name].append(parameters)

        # Trigger learning if enough samples
        if len(self._performance_history[strategy_name]) >= self.min_samples:
            self._learn(strategy_name)

    def _learn(self, strategy_name: str):
        """Learn from recent performance"""
        history = list(self._performance_history[strategy_name])

        # Group by parameter sets
        param_performance: Dict[str, List[float]] = {}

        for record in history:
            params_key = json.dumps(record["parameters"], sort_keys=True)
            pnl = record["result"].get("pnl", 0)

            if params_key not in param_performance:
                param_performance[params_key] = []
            param_performance[params_key].append(pnl)

        # Find best performing parameters
        best_params_key = None
        best_avg_pnl = float('-inf')

        for params_key, pnls in param_performance.items():
            if len(pnls) >= 5:  # Need minimum samples
                avg_pnl = statistics.mean(pnls)
                if avg_pnl > best_avg_pnl:
                    best_avg_pnl = avg_pnl
                    best_params_key = params_key

        if best_params_key:
            self._best_params[strategy_name] = json.loads(best_params_key)
            self._save_state()

            logger.info(
                f"Strategy {strategy_name} learned: "
                f"best avg PnL={best_avg_pnl:.2f}, "
                f"params={self._best_params[strategy_name]}"
            )

    def suggest_parameters(
        self,
        strategy_name: str,
        param_ranges: Dict[str, tuple]
    ) -> Dict:
        """
        Suggest parameters for next trade

        Uses exploration/exploitation balance
        """
        import random

        # Exploit: use best known parameters
        if strategy_name in self._best_params and random.random() > self.exploration_rate:
            return self._best_params[strategy_name].copy()

        # Explore: try new parameters
        suggested = {}
        for param, (min_val, max_val) in param_ranges.items():
            if isinstance(min_val, int):
                suggested[param] = random.randint(min_val, max_val)
            else:
                suggested[param] = random.uniform(min_val, max_val)

        return suggested

    def get_performance_summary(self, strategy_name: str) -> Dict:
        """Get strategy performance summary"""
        if strategy_name not in self._performance_history:
            return {"error": "No data"}

        history = list(self._performance_history[strategy_name])
        pnls = [r["result"].get("pnl", 0) for r in history]

        if not pnls:
            return {"error": "No trades"}

        wins = sum(1 for p in pnls if p > 0)

        return {
            "total_trades": len(pnls),
            "win_rate": wins / len(pnls) * 100,
            "total_pnl": sum(pnls),
            "avg_pnl": statistics.mean(pnls),
            "best_trade": max(pnls),
            "worst_trade": min(pnls),
            "std_dev": statistics.stdev(pnls) if len(pnls) > 1 else 0,
            "best_params": self._best_params.get(strategy_name)
        }


class RegimeDetector:
    """
    Market regime detection

    Detects:
    - Bull market
    - Bear market
    - Sideways/ranging
    - High volatility
    - Low volatility
    """

    class Regime(Enum):
        BULL = "bull"
        BEAR = "bear"
        SIDEWAYS = "sideways"
        HIGH_VOL = "high_volatility"
        LOW_VOL = "low_volatility"
        UNKNOWN = "unknown"

    def __init__(self, lookback_days: int = 30):
        self.lookback_days = lookback_days
        self._price_history: deque = deque(maxlen=lookback_days * 24)  # Hourly
        self._current_regime = self.Regime.UNKNOWN

    def update(self, price: float, timestamp: datetime = None):
        """Update with new price"""
        self._price_history.append({
            "price": price,
            "timestamp": timestamp or datetime.now(timezone.utc)
        })

        if len(self._price_history) >= 24:  # Need at least 24 hours
            self._current_regime = self._detect_regime()

    def _detect_regime(self) -> "RegimeDetector.Regime":
        """Detect current regime"""
        prices = [p["price"] for p in self._price_history]

        if len(prices) < 24:
            return self.Regime.UNKNOWN

        # Calculate returns
        returns = [(prices[i] - prices[i-1]) / prices[i-1]
                   for i in range(1, len(prices))]

        # Trend detection
        avg_return = statistics.mean(returns)
        volatility = statistics.stdev(returns) if len(returns) > 1 else 0

        # Price change over period
        price_change = (prices[-1] - prices[0]) / prices[0]

        # Classify
        if volatility > 0.03:  # High volatility threshold
            return self.Regime.HIGH_VOL
        elif volatility < 0.005:  # Low volatility threshold
            return self.Regime.LOW_VOL
        elif price_change > 0.1:  # 10% up
            return self.Regime.BULL
        elif price_change < -0.1:  # 10% down
            return self.Regime.BEAR
        else:
            return self.Regime.SIDEWAYS

    @property
    def current_regime(self) -> "RegimeDetector.Regime":
        return self._current_regime

    def get_strategy_adjustment(self) -> Dict:
        """Get strategy adjustments for current regime"""
        adjustments = {
            self.Regime.BULL: {
                "bias": "long",
                "position_size_multiplier": 1.2,
                "stop_loss_multiplier": 1.1,  # Wider stops
                "take_profit_multiplier": 1.3  # Larger targets
            },
            self.Regime.BEAR: {
                "bias": "short",
                "position_size_multiplier": 0.8,  # Smaller positions
                "stop_loss_multiplier": 0.9,  # Tighter stops
                "take_profit_multiplier": 0.8
            },
            self.Regime.SIDEWAYS: {
                "bias": "neutral",
                "position_size_multiplier": 0.7,
                "stop_loss_multiplier": 0.8,
                "take_profit_multiplier": 0.7
            },
            self.Regime.HIGH_VOL: {
                "bias": "neutral",
                "position_size_multiplier": 0.5,  # Reduce size in high vol
                "stop_loss_multiplier": 1.5,  # Much wider stops
                "take_profit_multiplier": 1.5
            },
            self.Regime.LOW_VOL: {
                "bias": "neutral",
                "position_size_multiplier": 1.0,
                "stop_loss_multiplier": 0.7,  # Tighter in low vol
                "take_profit_multiplier": 0.7
            }
        }

        return adjustments.get(self._current_regime, {
            "bias": "neutral",
            "position_size_multiplier": 1.0,
            "stop_loss_multiplier": 1.0,
            "take_profit_multiplier": 1.0
        })


class ResearchIngester:
    """
    Ingests research papers and market analysis

    Sources:
    - ArXiv preprints
    - CoinDesk research
    - Messari reports
    - Trading journals
    """

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data/research")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._research_cache: deque = deque(maxlen=200)  # Limit cached papers
        self._insights: deque = deque(maxlen=500)  # Limit stored insights

    async def fetch_arxiv_papers(
        self,
        query: str = "cryptocurrency trading",
        max_results: int = 10
    ) -> List[Dict]:
        """Fetch relevant papers from ArXiv"""
        import aiohttp

        papers = []
        base_url = "http://export.arxiv.org/api/query"

        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "search_query": f"all:{query}",
                    "start": 0,
                    "max_results": max_results,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending"
                }

                async with session.get(base_url, params=params) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        papers = self._parse_arxiv_response(text)

        except Exception as e:
            logger.error(f"Failed to fetch ArXiv papers: {e}")

        return papers

    def _parse_arxiv_response(self, xml_text: str) -> List[Dict]:
        """Parse ArXiv API response"""
        papers = []

        # Simple regex parsing (would use proper XML parser in production)
        entries = re.findall(r'<entry>(.*?)</entry>', xml_text, re.DOTALL)

        for entry in entries:
            title_match = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
            summary_match = re.search(r'<summary>(.*?)</summary>', entry, re.DOTALL)
            published_match = re.search(r'<published>(.*?)</published>', entry)
            id_match = re.search(r'<id>(.*?)</id>', entry)

            if title_match and summary_match:
                papers.append({
                    "title": title_match.group(1).strip(),
                    "summary": summary_match.group(1).strip()[:500],
                    "published": published_match.group(1) if published_match else "",
                    "url": id_match.group(1) if id_match else "",
                    "source": "arxiv"
                })

        return papers

    async def extract_insights(self, papers: List[Dict]) -> List[Dict]:
        """Extract actionable insights from papers"""
        insights = []

        # Keywords that indicate actionable findings
        action_keywords = [
            "outperform", "significant", "profitable", "alpha",
            "predict", "forecast", "correlation", "strategy"
        ]

        for paper in papers:
            summary_lower = paper.get("summary", "").lower()

            # Check for actionable content
            relevance_score = sum(1 for k in action_keywords if k in summary_lower)

            if relevance_score >= 2:
                insights.append({
                    "source": paper.get("url", ""),
                    "title": paper.get("title", ""),
                    "relevance_score": relevance_score,
                    "summary": paper.get("summary", "")[:300],
                    "extracted_at": datetime.now(timezone.utc).isoformat()
                })

        self._insights.extend(insights)
        return insights

    def get_strategy_recommendations(self) -> List[str]:
        """Get strategy recommendations from research"""
        # Analyze accumulated insights for recommendations
        recommendations = []

        # Example logic - would be more sophisticated in production
        keywords_to_recommendations = {
            "momentum": "Consider momentum-based strategies for trending markets",
            "mean reversion": "Mean reversion strategies may work in ranging markets",
            "sentiment": "Sentiment signals show predictive power for short-term moves",
            "volume": "Volume analysis can confirm breakout strength",
            "machine learning": "ML models outperform in pattern recognition tasks"
        }

        for insight in self._insights[-50:]:  # Recent insights
            summary = insight.get("summary", "").lower()
            for keyword, recommendation in keywords_to_recommendations.items():
                if keyword in summary and recommendation not in recommendations:
                    recommendations.append(recommendation)

        return recommendations


# Factory functions
def create_sentiment_analyzer() -> BaseSentimentAnalyzer:
    """Create sentiment analyzer with best available model"""
    return TransformerSentimentAnalyzer()


def create_ml_pipeline(data_dir: Path = None) -> Dict:
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
    "SentimentResult",
    "NewsEvent",
    "BaseSentimentAnalyzer",
    "TransformerSentimentAnalyzer",
    "CryptoNER",
    "NewsEventDetector",
    "StrategyLearner",
    "RegimeDetector",
    "ResearchIngester",
    "create_sentiment_analyzer",
    "create_ml_pipeline",
    "TRANSFORMERS_AVAILABLE"
]
