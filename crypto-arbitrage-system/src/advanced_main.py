"""
Advanced Arbitrage Bot with ML Scoring and Risk Management

Integrates:
- Advanced arbitrage engine with 6-factor ML scoring
- Almgren-Chriss slippage estimation
- Execution engine with circuit breakers
- Risk management with Kelly Criterion, VaR, Sharpe ratios
- Statistical arbitrage with cointegration
"""

import asyncio
import json
import logging
import logging.handlers
import signal
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timezone

import ccxt.pro as ccxtpro

from .core.advanced_engine import (
    AdvancedArbitrageEngine,
    EnhancedOrderBook,
    OpportunityScore
)
from .core.execution_engine import ExecutionEngine
from .core.risk_manager import RiskManager, TradeRecord
from .core.balance_manager import BalanceManager
from .core.state_manager import get_state_manager
from .database.connection import DatabasePool
from .utils.cache import RedisCache
from .utils.metrics import MetricsCollector
from .config.settings import load_config, ConfigLoadError, ConfigValidationError

# Import health server
try:
    from .api.health_server import HealthServer
    HEALTH_SERVER_AVAILABLE = True
except ImportError:
    HEALTH_SERVER_AVAILABLE = False

# Import optional modules with graceful fallbacks
try:
    from .core.antifragile import AntifragileCore
    ANTIFRAGILE_AVAILABLE = True
except ImportError:
    ANTIFRAGILE_AVAILABLE = False

try:
    from .signals import SignalManager, SentimentAggregator
    SIGNALS_AVAILABLE = True
except ImportError:
    SIGNALS_AVAILABLE = False

try:
    from .ml import MLAnalyzer
    ML_ANALYZER_AVAILABLE = True
except ImportError:
    ML_ANALYZER_AVAILABLE = False

try:
    from .notifications import NotificationManager
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False

try:
    from .compliance import ComplianceManager
    COMPLIANCE_AVAILABLE = True
except ImportError:
    COMPLIANCE_AVAILABLE = False

# Placeholder logger — reconfigured in setup_logging() once config is loaded
logger = logging.getLogger(__name__)


class _JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for machine-readable output."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def setup_logging(config_logging: dict) -> None:
    """Configure logging from config.yaml's ``logging`` section.

    Supports:
    - ``level``: DEBUG / INFO / WARNING / ERROR / CRITICAL
    - ``format``: ``json`` for structured output, anything else for text
    - ``file_enabled``: whether to write to disk
    - ``file_path``: log file location (relative OK)
    - ``max_file_size_mb``: per-file size cap before rotation
    - ``backup_count``: number of rotated files to keep
    """
    level_name = config_logging.get("level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = config_logging.get("format", "text")
    if fmt == "json":
        formatter = _JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # Build handler list
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if config_logging.get("file_enabled", True):
        log_path = Path(config_logging.get("file_path", "data/logs/arbitrage.log"))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        max_bytes = int(config_logging.get("max_file_size_mb", 100)) * 1024 * 1024
        backup_count = int(config_logging.get("backup_count", 5))
        handlers.append(
            logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
            )
        )

    # Apply to root logger
    root = logging.getLogger()
    root.setLevel(level)
    # Remove any pre-existing handlers (e.g. from basicConfig)
    for h in root.handlers[:]:
        root.removeHandler(h)
    for h in handlers:
        h.setFormatter(formatter)
        root.addHandler(h)


class AdvancedArbitrageBot:
    """
    Advanced arbitrage bot with ML-based opportunity scoring and risk management
    """

    def __init__(self):
        self.config = None
        self.exchanges = {}
        self.db_pool = None
        self.cache = None
        self.metrics = None

        # Advanced components
        self.advanced_engine = None
        self.execution_engine = None
        self.risk_manager = None
        self.balance_manager = None
        self.state_manager = None

        # Optional integrated modules
        self.antifragile = None
        self.signal_manager = None
        self.sentiment_aggregator = None
        self.ml_analyzer = None
        self.notification_manager = None
        self.compliance_manager = None

        # Health server for Kubernetes probes
        self.health_server = None

        self.running = False
        self.shutdown_event = asyncio.Event()

        # Persistent WebSocket orderbook cache: {(exchange, symbol): EnhancedOrderBook}
        # Note: dict[key] assignment is atomic within asyncio's single-threaded event loop
        # (no preemptive context switch during assignment), so no lock is needed.
        self._latest_orderbooks = {}
        # Event fired when any orderbook updates for a given symbol: {symbol: asyncio.Event}
        self._orderbook_events = {}

        # Tracking
        self.opportunities_detected = 0
        self.opportunities_scored = 0
        self.opportunities_executed = 0

    async def initialize(self):
        """Initialize all components"""
        logger.info("🚀 Initializing Advanced Arbitrage Bot...")

        # Load configuration with proper error handling
        try:
            self.config = load_config()
        except ConfigLoadError as e:
            logger.error(f"Failed to load configuration: {e}")
            raise SystemExit(1)
        except ConfigValidationError as e:
            logger.error(f"Invalid configuration: {e}")
            raise SystemExit(1)

        # Apply logging config (RotatingFileHandler, level, format) now that config is loaded
        logging_cfg = getattr(self.config, 'logging', None) or {}
        setup_logging(logging_cfg)

        # Initialize state manager first for cross-component communication
        self.state_manager = get_state_manager()
        self.state_manager.update_trading_state(
            mode=self.config.trading.mode,
            initial_capital=Decimal(str(self.config.trading.max_position_usd * 20))
        )
        logger.info("✓ State manager initialized")

        # Initialize database pool
        self.db_pool = DatabasePool(self.config.database)
        await self.db_pool.connect()
        self.state_manager.update_system_health(database_connected=True)

        # Initialize Redis cache
        self.cache = RedisCache(self.config.redis)
        await self.cache.connect()
        self.state_manager.update_system_health(redis_connected=True)

        # Initialize metrics collector
        self.metrics = MetricsCollector(self.config.monitoring['prometheus_port'])
        self.state_manager.update_system_health(prometheus_running=True)

        # Initialize exchanges
        await self._initialize_exchanges()

        # Initialize health server for Kubernetes probes
        if HEALTH_SERVER_AVAILABLE:
            try:
                health_port = self.config.monitoring.get('health_port', 8080)
                self.health_server = HealthServer(
                    port=health_port,
                    db_pool=self.db_pool,
                    redis_client=self.cache,
                    exchanges=self.exchanges,
                    version="1.0.0"
                )
                await self.health_server.start()
                logger.info(f"✓ Health server started on port {health_port}")
            except Exception as e:
                logger.warning(f"⚠ Health server failed to start: {e}")

        # Initialize balance manager for pre-trade validation
        self.balance_manager = BalanceManager(
            exchanges=self.exchanges,
            refresh_interval=self.config.performance.get('balance_update_interval_seconds', 30),
            stale_threshold=60
        )
        await self.balance_manager.start()
        logger.info("✓ Balance manager initialized")

        # Initialize advanced components
        self.advanced_engine = AdvancedArbitrageEngine(self.config)
        self.execution_engine = ExecutionEngine(
            self.config, self.exchanges, balance_manager=self.balance_manager
        )
        self.risk_manager = RiskManager(self.config)

        # Initialize optional integrated modules
        await self._initialize_optional_modules()

        logger.info(f"✅ Initialized {len(self.exchanges)} exchanges")
        logger.info(f"📊 Monitoring: {', '.join(self.config.symbols)}")
        logger.info(f"🎯 Min spread: {self.config.trading.min_spread_percent}%")
        logger.info(f"📝 Mode: {'PAPER TRADING' if self.config.trading.mode == 'paper' else 'LIVE TRADING'}")

        features = ["ML Scoring", "Risk Management", "Circuit Breakers"]
        if self.health_server:
            features.append("Health Server")
        if self.antifragile:
            features.append("Antifragile Adaptation")
        if self.signal_manager:
            features.append("Signal Analysis")
        if self.notification_manager:
            features.append("Notifications")

        logger.info(f"✨ Advanced features: {', '.join(features)}")

        # Update state manager with connected exchanges
        self.state_manager.update_trading_state(
            exchanges_connected=list(self.exchanges.keys())
        )

    async def _initialize_optional_modules(self):
        """Initialize optional integrated modules"""

        # Antifragile Core - Self-learning and adaptation
        if ANTIFRAGILE_AVAILABLE:
            try:
                self.antifragile = AntifragileCore(self.config)
                await self.antifragile.initialize()
                logger.info("✓ Antifragile module initialized")
            except Exception as e:
                logger.warning(f"⚠ Antifragile module failed: {e}")

        # Signal Manager - Sentiment and news analysis
        if SIGNALS_AVAILABLE:
            try:
                self.signal_manager = SignalManager(self.config)
                self.sentiment_aggregator = SentimentAggregator()
                logger.info("✓ Signal/Sentiment module initialized")
            except Exception as e:
                logger.warning(f"⚠ Signal module failed: {e}")

        # ML Analyzer - Deep learning sentiment
        if ML_ANALYZER_AVAILABLE:
            try:
                self.ml_analyzer = MLAnalyzer()
                logger.info("✓ ML Analyzer initialized")
            except Exception as e:
                logger.warning(f"⚠ ML Analyzer failed: {e}")

        # Notification Manager - Alerts
        if NOTIFICATIONS_AVAILABLE:
            try:
                self.notification_manager = NotificationManager(self.config)
                logger.info("✓ Notification module initialized")
            except Exception as e:
                logger.warning(f"⚠ Notification module failed: {e}")

        # Compliance Manager - Tax and audit
        if COMPLIANCE_AVAILABLE:
            try:
                self.compliance_manager = ComplianceManager()
                logger.info("✓ Compliance module initialized")
            except Exception as e:
                logger.warning(f"⚠ Compliance module failed: {e}")

    async def _initialize_exchanges(self):
        """Initialize exchange connections"""
        failed_exchanges = []

        for exchange_name, exchange_config in self.config.exchanges.items():
            if not exchange_config.get('enabled', True):
                continue

            try:
                exchange_class = getattr(ccxtpro, exchange_name)
                exchange = exchange_class({
                    'enableRateLimit': True,
                    'options': {'defaultType': 'spot'},
                })

                # Test connection
                await exchange.load_markets()
                self.exchanges[exchange_name] = exchange
                logger.info(f"✓ Connected to {exchange_name}")

            except Exception as e:
                logger.error(f"✗ Failed to connect to {exchange_name}: {e}")
                failed_exchanges.append(exchange_name)

        # Fail fast if no exchanges connected - critical for arbitrage
        if not self.exchanges:
            raise RuntimeError(
                f"No exchanges connected. Failed: {failed_exchanges}. "
                "Cannot operate arbitrage without exchange connections."
            )

        # Warn if some exchanges failed but continue if we have at least 2
        if failed_exchanges and len(self.exchanges) < 2:
            raise RuntimeError(
                f"Only {len(self.exchanges)} exchange(s) connected, need at least 2 for arbitrage. "
                f"Failed: {failed_exchanges}"
            )

    async def _stream_orderbook(self, exchange_name: str, symbol: str):
        """Persistent WebSocket stream for one exchange/symbol pair.

        Continuously calls watch_order_book (ccxt.pro's blocking WS call)
        and stores the latest snapshot in-memory for the scanner to read.
        """
        exchange = self.exchanges[exchange_name]
        backoff = 1
        max_backoff = 30

        while self.running:
            try:
                ob_data = await exchange.watch_order_book(symbol)
                now = datetime.now(timezone.utc)

                orderbook = EnhancedOrderBook(
                    exchange=exchange_name,
                    symbol=symbol,
                    timestamp=now,
                    bids=[(Decimal(str(p)), Decimal(str(v))) for p, v in ob_data['bids'][:20]],
                    asks=[(Decimal(str(p)), Decimal(str(v))) for p, v in ob_data['asks'][:20]]
                )

                # Store in-memory (atomic within asyncio's single-threaded event loop)
                self._latest_orderbooks[(exchange_name, symbol)] = orderbook

                # Update price history for cointegration analysis
                self.advanced_engine.update_price_history(
                    exchange_name, symbol, orderbook.mid_price, now
                )

                # Signal the scanner that new data is available for this symbol
                event = self._orderbook_events.get(symbol)
                if event:
                    event.set()

                self.metrics.increment('orderbooks_fetched')
                backoff = 1  # Reset backoff on success

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WS stream error {exchange_name}:{symbol}: {e}")
                self.metrics.increment('orderbook_errors')
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

        logger.info(f"WS stream stopped: {exchange_name}:{symbol}")

    def fetch_orderbook_sync(self, exchange_name: str, symbol: str) -> EnhancedOrderBook:
        """Read latest orderbook from in-memory WS cache (non-blocking).

        Returns None if no data or data is stale (>5s).
        """
        ob = self._latest_orderbooks.get((exchange_name, symbol))
        if ob is None:
            return None

        age = (datetime.now(timezone.utc) - ob.timestamp).total_seconds()
        if age > 5.0:
            logger.debug(f"Rejecting stale orderbook {exchange_name}:{symbol} ({age:.1f}s old)")
            self.metrics.increment('orderbook_stale_rejects')
            return None

        self.metrics.increment('orderbook_cache_hits')
        return ob

    async def fetch_orderbook(self, exchange_name: str, symbol: str) -> EnhancedOrderBook:
        """Fetch orderbook — reads from persistent WS cache first, falls back to on-demand fetch."""
        # Fast path: read from in-memory WS stream cache
        ob = self.fetch_orderbook_sync(exchange_name, symbol)
        if ob is not None:
            return ob

        # Fallback: direct WS call (for startup or after stream reconnection)
        try:
            exchange = self.exchanges[exchange_name]
            ob_data = await exchange.watch_order_book(symbol)

            orderbook = EnhancedOrderBook(
                exchange=exchange_name,
                symbol=symbol,
                timestamp=datetime.now(timezone.utc),
                bids=[(Decimal(str(p)), Decimal(str(v))) for p, v in ob_data['bids'][:20]],
                asks=[(Decimal(str(p)), Decimal(str(v))) for p, v in ob_data['asks'][:20]]
            )

            self._latest_orderbooks[(exchange_name, symbol)] = orderbook

            self.advanced_engine.update_price_history(
                exchange_name, symbol, orderbook.mid_price, orderbook.timestamp
            )

            self.metrics.increment('orderbooks_fetched')
            return orderbook

        except Exception as e:
            logger.error(f"Error fetching {exchange_name} {symbol} orderbook: {e}")
            self.metrics.increment('orderbook_errors')
            return None

    async def find_and_score_arbitrage(self, symbol: str):
        """
        Find arbitrage opportunities and score them with ML-based system

        Returns best opportunity if score > threshold
        """
        # Fetch all orderbooks concurrently
        tasks = [
            self.fetch_orderbook(ex_name, symbol)
            for ex_name in self.exchanges.keys()
        ]
        orderbooks = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter valid orderbooks, logging any exceptions from failed fetches
        valid_orderbooks = []
        for ob in orderbooks:
            if isinstance(ob, Exception):
                logger.warning(f"Orderbook fetch failed for {symbol}: {ob}")
                self.metrics.increment('orderbook_fetch_errors')
            elif isinstance(ob, EnhancedOrderBook):
                valid_orderbooks.append(ob)

        if len(valid_orderbooks) < 2:
            return None

        # Find best opportunity across all pairs
        best_opportunity = None
        best_score = 0.0

        min_spread = Decimal(str(self.config.trading.min_spread_percent)) / 100
        position_size = Decimal(str(self.config.trading.max_position_usd))

        # Early exit threshold - if we find a score above this, take it immediately
        EXCELLENT_SCORE_THRESHOLD = 0.85

        for buy_ob in valid_orderbooks:
            # Early exit if we already found an excellent opportunity
            if best_score >= EXCELLENT_SCORE_THRESHOLD:
                break

            for sell_ob in valid_orderbooks:
                if buy_ob.exchange == sell_ob.exchange:
                    continue

                # Calculate gross spread
                buy_price, _ = buy_ob.best_ask
                sell_price, _ = sell_ob.best_bid

                if buy_price == 0 or sell_price == 0:
                    continue

                gross_spread = (sell_price - buy_price) / buy_price

                # Quick pre-filter: Skip if gross spread can't possibly meet min after fees
                # Typical fees are ~0.1% per side, so need at least min_spread + 0.2%
                if gross_spread < min_spread:
                    continue

                # Get exchange fees
                buy_fee = Decimal(str(self.config.exchanges[buy_ob.exchange].get('taker_fee', 0.001)))
                sell_fee = Decimal(str(self.config.exchanges[sell_ob.exchange].get('taker_fee', 0.001)))

                # Estimate slippage using Almgren-Chriss
                buy_slippage = self.advanced_engine.slippage_model.estimate_slippage(
                    position_size, buy_ob
                )
                sell_slippage = self.advanced_engine.slippage_model.estimate_slippage(
                    position_size, sell_ob
                )

                # Calculate net spread
                net_spread = gross_spread - buy_fee - sell_fee - buy_slippage - sell_slippage

                if net_spread < min_spread:
                    continue

                # Score the opportunity using 6-factor ML system
                score = self.advanced_engine.score_opportunity(
                    buy_orderbook=buy_ob,
                    sell_orderbook=sell_ob,
                    gross_spread=gross_spread,
                    net_spread=net_spread,
                    position_size_usd=position_size,
                    min_spread=min_spread
                )

                self.opportunities_scored += 1

                # Keep track of best opportunity
                if score.composite_score > best_score:
                    best_score = score.composite_score
                    best_opportunity = {
                        'symbol': symbol,
                        'buy_exchange': buy_ob.exchange,
                        'sell_exchange': sell_ob.exchange,
                        'buy_price': buy_price,
                        'sell_price': sell_price,
                        'buy_orderbook': buy_ob,
                        'sell_orderbook': sell_ob,
                        'gross_spread': gross_spread,
                        'net_spread': net_spread,
                        'spread_percent': net_spread * 100,
                        'buy_fee': buy_fee,
                        'sell_fee': sell_fee,
                        'buy_slippage': buy_slippage,
                        'sell_slippage': sell_slippage,
                        'score': score,
                        'position_size': position_size
                    }

                    # Early exit for excellent opportunities
                    if best_score >= EXCELLENT_SCORE_THRESHOLD:
                        break

        # Return opportunity if score meets threshold
        if best_opportunity and best_score >= 0.6:  # 60% score threshold
            self.opportunities_detected += 1

            # Update state manager
            self.state_manager.update_trading_state(
                opportunities_detected=self.opportunities_detected,
                opportunities_scored=self.opportunities_scored
            )

            # Record opportunity for dashboard
            self.state_manager.record_opportunity({
                'symbol': symbol,
                'buy_exchange': best_opportunity['buy_exchange'],
                'sell_exchange': best_opportunity['sell_exchange'],
                'spread_percent': float(best_opportunity['spread_percent']),
                'score': best_score,
                'buy_price': float(best_opportunity['buy_price']),
                'sell_price': float(best_opportunity['sell_price'])
            })

            return best_opportunity

        return None

    async def execute_opportunity(self, opportunity: dict):
        """Execute an arbitrage opportunity with risk management"""
        symbol = opportunity['symbol']
        score = opportunity['score']

        logger.info(
            f"\n{'='*80}\n"
            f"✨ HIGH-QUALITY OPPORTUNITY DETECTED\n"
            f"{'='*80}\n"
            f"Symbol: {symbol}\n"
            f"Route: Buy {opportunity['buy_exchange']} @ ${opportunity['buy_price']:.2f} -> "
            f"Sell {opportunity['sell_exchange']} @ ${opportunity['sell_price']:.2f}\n"
            f"Spread: {opportunity['spread_percent']:.3f}%\n"
            f"{'='*80}\n"
            f"ML SCORE BREAKDOWN:\n"
            f"  Composite Score:      {score.composite_score:.3f} (Confidence: {score.confidence:.3f})\n"
            f"  - Spread Score:       {score.spread_score:.3f} (35% weight)\n"
            f"  - Liquidity Score:    {score.liquidity_score:.3f} (25% weight)\n"
            f"  - Volatility Score:   {score.volatility_score:.3f} (15% weight)\n"
            f"  - Timing Score:       {score.timing_score:.3f} (10% weight)\n"
            f"  - Exchange Quality:   {score.exchange_quality_score:.3f} (10% weight)\n"
            f"  - Cointegration:      {score.cointegration_score:.3f} (5% weight)\n"
            f"{'='*80}"
        )

        # Check risk limits
        allowed, reason = self.risk_manager.check_risk_limits()
        if not allowed:
            logger.warning(f"⚠️  Trade blocked by risk manager: {reason}")
            return

        # Calculate position risk
        volatility = self.advanced_engine.price_history.calculate_volatility(
            opportunity['buy_exchange'], symbol
        )

        position_risk = self.risk_manager.calculate_position_risk(
            symbol=symbol,
            expected_spread=opportunity['net_spread'],
            expected_fees=opportunity['buy_fee'] + opportunity['sell_fee'],
            volatility=volatility
        )

        logger.info(
            f"\n{'='*80}\n"
            f"RISK ANALYSIS:\n"
            f"  Recommended Size:     ${position_risk.recommended_size:.2f}\n"
            f"  Kelly Optimal:        ${position_risk.optimal_size_kelly:.2f}\n"
            f"  Win Probability:      {position_risk.win_probability:.1%}\n"
            f"  Expected Return:      ${position_risk.expected_return * position_risk.recommended_size:.2f}\n"
            f"  Risk Score:           {position_risk.risk_score:.3f}\n"
            f"  Position Sharpe:      {position_risk.sharpe_ratio:.2f}\n"
            f"{'='*80}"
        )

        # Reduce risk if needed
        if self.risk_manager.should_reduce_risk():
            position_risk.recommended_size *= Decimal('0.5')
            logger.warning(f"⚠️  Reducing position size to ${position_risk.recommended_size:.2f}")

        # Execute the trade
        logger.info(f"🎯 Executing trade with ${position_risk.recommended_size:.2f}...")

        amount = position_risk.recommended_size / opportunity['buy_price']

        result = await self.execution_engine.execute_arbitrage(
            buy_exchange=opportunity['buy_exchange'],
            sell_exchange=opportunity['sell_exchange'],
            symbol=symbol,
            buy_price=opportunity['buy_price'],
            sell_price=opportunity['sell_price'],
            amount=amount,
            buy_orderbook=opportunity.get('buy_orderbook'),
            sell_orderbook=opportunity.get('sell_orderbook'),
            max_slippage_percent=Decimal('0.5')
        )

        if result.success:
            self.opportunities_executed += 1

            # Record trade in risk manager
            trade = TradeRecord(
                timestamp=datetime.now(timezone.utc),
                symbol=symbol,
                buy_exchange=opportunity['buy_exchange'],
                sell_exchange=opportunity['sell_exchange'],
                position_size=position_risk.recommended_size,
                gross_profit=result.gross_profit,
                net_profit=result.net_profit,
                fees=result.total_fees,
                execution_time_ms=result.execution_time_ms,
                success=True
            )
            self.risk_manager.record_trade(trade)

            # Save to database
            await self._save_execution(opportunity, result, score)

            # Update state manager
            portfolio_risk = self.risk_manager.calculate_portfolio_risk()
            self.state_manager.update_trading_state(
                opportunities_executed=self.opportunities_executed,
                total_profit=Decimal(str(result.net_profit)) + self.state_manager.get_trading_state().total_profit,
                win_rate=portfolio_risk.win_rate,
                sharpe_ratio=portfolio_risk.sharpe_ratio,
                sortino_ratio=portfolio_risk.sortino_ratio,
                var_95=Decimal(str(portfolio_risk.var_95)),
                total_trades=portfolio_risk.total_trades,
                successful_trades=int(portfolio_risk.total_trades * portfolio_risk.win_rate)
            )

            # Record trade in state manager for dashboard
            self.state_manager.record_trade({
                'symbol': symbol,
                'buy_exchange': opportunity['buy_exchange'],
                'sell_exchange': opportunity['sell_exchange'],
                'net_profit': float(result.net_profit),
                'gross_profit': float(result.gross_profit),
                'execution_time_ms': result.execution_time_ms,
                'success': True,
                'score': score.composite_score
            })

            # Record in compliance if available - important for audit trail
            if self.compliance_manager:
                try:
                    await self.compliance_manager.record_trade(
                        symbol=symbol,
                        side='arbitrage',
                        quantity=float(position_risk.recommended_size / opportunity['buy_price']),
                        price=float(opportunity['buy_price']),
                        cost_basis=float(position_risk.recommended_size),
                        proceeds=float(position_risk.recommended_size + result.net_profit)
                    )
                except Exception as e:
                    # Compliance failures need attention for regulatory reasons
                    logger.error(
                        f"Compliance recording failed for {symbol} trade: {e}. "
                        "Manual audit entry may be required.",
                        exc_info=True
                    )
                    if self.state_manager:
                        self.state_manager.record_error(f"Compliance recording failed: {e}")

            # Send notification if available
            if self.notification_manager:
                try:
                    await self.notification_manager.send_trade_alert(
                        symbol=symbol,
                        profit=float(result.net_profit),
                        buy_exchange=opportunity['buy_exchange'],
                        sell_exchange=opportunity['sell_exchange'],
                        execution_time_ms=result.execution_time_ms
                    )
                except Exception as e:
                    logger.warning(f"Notification failed: {e}")

            # Update antifragile learning if available
            if self.antifragile:
                try:
                    self.antifragile.record_outcome(
                        symbol=symbol,
                        success=True,
                        profit=float(result.net_profit),
                        score=score.composite_score,
                        market_conditions={
                            'volatility': float(volatility),
                            'spread': float(opportunity['net_spread']),
                            'liquidity': score.liquidity_score
                        }
                    )
                except Exception as e:
                    logger.warning(f"Antifragile update failed: {e}")

            # Log success with portfolio stats
            logger.info(
                f"\n{'='*80}\n"
                f"✅ TRADE EXECUTED SUCCESSFULLY\n"
                f"{'='*80}\n"
                f"Net Profit:           ${result.net_profit:.2f}\n"
                f"Execution Time:       {result.execution_time_ms}ms\n"
                f"{'='*80}\n"
                f"PORTFOLIO STATS:\n"
                f"  Total Trades:       {portfolio_risk.total_trades}\n"
                f"  Win Rate:           {portfolio_risk.win_rate:.1%}\n"
                f"  Sharpe Ratio:       {portfolio_risk.sharpe_ratio:.2f}\n"
                f"  Sortino Ratio:      {portfolio_risk.sortino_ratio:.2f}\n"
                f"  VaR (95%):          ${portfolio_risk.var_95:.2f}\n"
                f"  Max Drawdown:       {portfolio_risk.max_drawdown_percent:.1%}\n"
                f"  Profit Factor:      {portfolio_risk.profit_factor:.2f}\n"
                f"{'='*80}\n"
            )
        else:
            logger.error(f"❌ Trade execution failed: {result.error_message}")
            self.state_manager.record_error(f"Trade failed: {result.error_message}")

    async def _save_execution(self, opportunity: dict, result, score: OpportunityScore):
        """Save opportunity and execution to database"""
        try:
            async with self.db_pool.acquire() as conn:
                # Use explicit transaction to ensure atomicity —
                # if execution INSERT fails, opportunity INSERT is rolled back too
                async with conn.transaction():
                    # Insert opportunity (matches opportunities schema in models.py)
                    spread_bps = Decimal(str(opportunity['spread_percent'])) * 100
                    quantity = Decimal(str(opportunity['position_size'])) / Decimal(str(opportunity['buy_price']))
                    opp_id = await conn.fetchval("""
                    INSERT INTO opportunities
                    (symbol, buy_exchange, sell_exchange,
                     buy_price, sell_price, spread_bps,
                     available_quantity, score, executed, discovered_at,
                     metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    RETURNING id
                """,
                    opportunity['symbol'],
                    opportunity['buy_exchange'],
                    opportunity['sell_exchange'],
                    Decimal(str(opportunity['buy_price'])),
                    Decimal(str(opportunity['sell_price'])),
                    spread_bps,
                    quantity,
                    Decimal(str(score.composite_score)),
                    True,
                    datetime.now(timezone.utc),
                    json.dumps({
                        'buy_fee_percent': str(opportunity['buy_fee'] * 100),
                        'sell_fee_percent': str(opportunity['sell_fee'] * 100),
                        'slippage_estimate': str((opportunity['buy_slippage'] + opportunity['sell_slippage']) * 100),
                        'net_spread': str(opportunity['net_spread']),
                    })
                )

                    # Insert execution (matches arbitrage_executions schema in models.py)
                    buy_fee = Decimal(str(result.buy_order.fee))
                    sell_fee = Decimal(str(result.sell_order.fee))
                    await conn.execute("""
                        INSERT INTO arbitrage_executions
                        (symbol, buy_exchange, sell_exchange,
                         buy_price, sell_price, spread_bps,
                         quantity, gross_profit, total_fees, net_profit,
                         success, total_execution_time_ms,
                         completed_at, opportunity_id, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14::text, $15)
                    """,
                        opportunity['symbol'],
                        opportunity['buy_exchange'],
                        opportunity['sell_exchange'],
                        Decimal(str(result.buy_order.avg_fill_price)),
                        Decimal(str(result.sell_order.avg_fill_price)),
                        spread_bps,
                        Decimal(str(result.buy_order.filled_amount)),
                        Decimal(str(result.gross_profit)),
                        buy_fee + sell_fee,
                        Decimal(str(result.net_profit)),
                        True,
                        result.execution_time_ms,
                        datetime.now(timezone.utc),
                        str(opp_id),
                        json.dumps({
                            'buy_filled_amount': str(result.buy_order.filled_amount),
                            'sell_filled_amount': str(result.sell_order.filled_amount),
                            'buy_fee': str(result.buy_order.fee),
                            'sell_fee': str(result.sell_order.fee),
                        })
                    )

        except Exception as e:
            # Database persistence failure is serious - log with full context for investigation
            logger.error(
                f"CRITICAL: Failed to save execution to database: {e}. "
                f"Trade details - Symbol: {opportunity['symbol']}, "
                f"Buy: {opportunity['buy_exchange']}, Sell: {opportunity['sell_exchange']}, "
                f"Profit: ${result.net_profit:.2f}",
                exc_info=True
            )
            # Record error in state manager for monitoring
            if self.state_manager:
                self.state_manager.record_error(
                    f"Database persistence failed for trade on {opportunity['symbol']}: {e}"
                )

    async def monitor_symbol(self, symbol: str):
        """Continuously monitor one symbol, driven by WebSocket orderbook updates.

        Waits for the WS stream to signal new data (via asyncio.Event) instead of
        polling with a fixed sleep interval. Falls back to check_interval_seconds
        timeout so we still scan periodically even if the event is missed.
        """
        check_interval = self.config.performance.get('check_interval_seconds', 2)
        logger.info(f"👀 Monitoring {symbol} (event-driven, fallback {check_interval}s)...")

        # Use pre-created event (initialized in run() before streams start)
        event = self._orderbook_events[symbol]

        while self.running:
            try:
                # Wait for WS update or timeout after check_interval (whichever comes first)
                try:
                    await asyncio.wait_for(event.wait(), timeout=check_interval)
                except asyncio.TimeoutError:
                    pass  # Scan anyway on timeout
                event.clear()

                # Find and score opportunities using latest WS-cached orderbooks
                opportunity = await self.find_and_score_arbitrage(symbol)

                if opportunity:
                    await self.execute_opportunity(opportunity)

            except Exception as e:
                logger.error(f"Error monitoring {symbol}: {e}", exc_info=True)
                await asyncio.sleep(2)

    async def print_stats(self):
        """Periodically print statistics"""
        while self.running:
            await asyncio.sleep(60)  # Every minute

            # Get execution stats
            exec_stats = self.execution_engine.get_execution_stats()

            # Get risk summary
            risk_summary = self.risk_manager.get_risk_summary()

            logger.info(
                f"\n{'='*80}\n"
                f"SYSTEM STATISTICS (1-minute update)\n"
                f"{'='*80}\n"
                f"Opportunities:\n"
                f"  Detected:           {self.opportunities_detected}\n"
                f"  Scored (ML):        {self.opportunities_scored}\n"
                f"  Executed:           {self.opportunities_executed}\n"
                f"\nExecution:\n"
                f"  Total Attempts:     {exec_stats['total_executions']}\n"
                f"  Success Rate:       {exec_stats['success_rate']:.1%}\n"
                f"  Avg Time:           {exec_stats['avg_execution_time_ms']}ms\n"
                f"  Total Profit:       ${exec_stats['total_profit']:.2f}\n"
                f"\nPortfolio:\n"
                f"  Capital:            ${risk_summary['current_capital']:.2f}\n"
                f"  Win Rate:           {risk_summary['win_rate']}\n"
                f"  Sharpe Ratio:       {risk_summary['sharpe_ratio']}\n"
                f"  Max Drawdown:       {risk_summary['max_drawdown']}\n"
                f"  VaR (95%):          {risk_summary['var_95']}\n"
                f"{'='*80}\n"
            )

    async def run(self):
        """Main execution loop"""
        self.running = True
        await self.initialize()

        # Update state manager
        self.state_manager.update_trading_state(running=True)

        tasks = []

        # Pre-create events for all symbols BEFORE starting streams,
        # so streams can signal monitors from the very first update.
        for symbol in self.config.symbols:
            self._orderbook_events[symbol] = asyncio.Event()

        # Start persistent WebSocket orderbook streams (1 per exchange/symbol pair)
        for exchange_name in self.exchanges:
            for symbol in self.config.symbols:
                tasks.append(self._stream_orderbook(exchange_name, symbol))

        logger.info(
            f"Started {len(tasks)} WebSocket streams for "
            f"{len(self.exchanges)} exchanges × {len(self.config.symbols)} symbols"
        )

        # Monitor all symbols in parallel (event-driven by WS updates)
        for symbol in self.config.symbols:
            tasks.append(self.monitor_symbol(symbol))

        # Add stats printer
        tasks.append(self.print_stats())

        # Add sentiment monitoring if signal module available
        if self.signal_manager and self.sentiment_aggregator:
            tasks.append(self._monitor_sentiment())

        # Add antifragile adaptation if available
        if self.antifragile:
            tasks.append(self._run_antifragile_adaptation())

        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Log any top-level task failures (streams/monitors that crashed unexpectedly)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {i} failed with unhandled exception: {result}", exc_info=result)

    async def _monitor_sentiment(self):
        """Monitor market sentiment and update state"""
        while self.running:
            try:
                # Aggregate sentiment from various sources
                market_sentiment = await self.sentiment_aggregator.get_market_sentiment()

                # Update state manager with sentiment
                self.state_manager.update_signal_state(
                    market_sentiment=market_sentiment.overall_score,
                    market_trend=market_sentiment.trend
                )

                # Get asset-specific sentiment
                for symbol in self.config.symbols:
                    base_asset = symbol.replace('USDT', '').replace('/', '')
                    asset_sentiment = await self.sentiment_aggregator.get_asset_sentiment(base_asset)
                    if asset_sentiment:
                        current = self.state_manager.get_signal_state().asset_sentiment
                        current[base_asset.lower()] = asset_sentiment.score
                        self.state_manager.update_signal_state(asset_sentiment=current)

                # Check for trading signals
                signals = await self.signal_manager.get_active_signals()
                for signal in signals:
                    self.state_manager.add_active_signal({
                        'asset': signal.get('symbol', 'UNKNOWN'),
                        'type': signal.get('direction', 'neutral'),
                        'confidence': signal.get('confidence', 0.5),
                        'source': signal.get('source', 'sentiment')
                    })

                await asyncio.sleep(60)  # Update every minute

            except Exception as e:
                logger.warning(f"Sentiment monitoring error: {e}")
                await asyncio.sleep(120)  # Backoff on error

    async def _run_antifragile_adaptation(self):
        """Run antifragile parameter adaptation"""
        while self.running:
            try:
                # Run adaptation cycle
                adaptations = await self.antifragile.run_adaptation_cycle()

                if adaptations:
                    logger.info(f"🔄 Antifragile adaptations proposed: {adaptations}")

                    # Only allow mutation of tunable runtime parameters
                    # (never mode, never the CLASS-LEVEL safety constants)
                    TUNABLE_PARAMS = frozenset({
                        'min_spread_percent', 'max_spread_percent',
                        'max_position_usd', 'max_daily_loss_usd',
                        'max_daily_trades', 'order_timeout_seconds',
                        'max_slippage_bps',
                    })
                    for param, value in adaptations.items():
                        if param not in TUNABLE_PARAMS:
                            logger.warning(
                                f"Antifragile adaptation rejected: '{param}' is not a tunable parameter"
                            )
                            continue

                        # Snapshot current value so we can rollback on validation failure
                        old_value = getattr(self.config.trading, param)
                        setattr(self.config.trading, param, value)
                        try:
                            # Re-run the full validation that __post_init__ performs
                            self.config.trading.__post_init__()
                            logger.info(f"  Applied: {param} = {value}")
                        except Exception as validation_err:
                            # Rollback to previous value
                            setattr(self.config.trading, param, old_value)
                            logger.warning(
                                f"Antifragile adaptation rejected: {param}={value} "
                                f"failed validation: {validation_err}"
                            )

                # Run stress test periodically
                stress_results = await self.antifragile.run_stress_test()
                if stress_results.get('risk_level', 0) > 0.8:
                    logger.warning(f"⚠️ High stress detected: {stress_results}")
                    self.state_manager.update_signal_state(
                        current_regime='volatile',
                        regime_confidence=stress_results.get('confidence', 0.5)
                    )

                await asyncio.sleep(300)  # Adapt every 5 minutes

            except Exception as e:
                logger.warning(f"Antifragile adaptation error: {e}")
                await asyncio.sleep(600)  # Backoff on error

    async def shutdown(self):
        """Cleanup and close connections"""
        logger.info("🛑 Shutting down...")
        self.running = False

        # Update state manager
        if self.state_manager:
            self.state_manager.update_trading_state(running=False)

        # Print final stats
        logger.info("\n" + "="*80)
        logger.info("FINAL STATISTICS")
        logger.info("="*80)

        exec_stats = self.execution_engine.get_execution_stats()
        risk_summary = self.risk_manager.get_risk_summary()

        logger.info(f"Opportunities Detected: {self.opportunities_detected}")
        logger.info(f"Opportunities Executed: {self.opportunities_executed}")
        logger.info(f"Execution Success Rate: {exec_stats['success_rate']:.1%}")
        logger.info(f"Total Profit: ${exec_stats['total_profit']:.2f}")
        logger.info(f"Final Capital: ${risk_summary['current_capital']:.2f}")
        logger.info(f"Sharpe Ratio: {risk_summary['sharpe_ratio']}")
        logger.info("="*80 + "\n")

        # Shutdown health server
        if self.health_server:
            try:
                await self.health_server.stop()
                logger.info("✓ Health server stopped")
            except Exception as e:
                logger.warning(f"Health server shutdown error: {e}")

        # Shutdown optional modules
        if self.antifragile:
            try:
                await self.antifragile.shutdown()
                logger.info("✓ Antifragile module shutdown")
            except Exception as e:
                logger.warning(f"Antifragile shutdown error: {e}")

        if self.notification_manager:
            try:
                await self.notification_manager.send_system_alert(
                    "CARBS System Shutdown",
                    f"Final P&L: ${exec_stats['total_profit']:.2f}"
                )
            except Exception as e:
                logger.warning(f"Notification error: {e}")

        # Stop balance manager
        if self.balance_manager:
            await self.balance_manager.stop()
            logger.info("✓ Balance manager stopped")

        # Close exchange connections
        for exchange in self.exchanges.values():
            await exchange.close()

        # Close database pool
        if self.db_pool:
            await self.db_pool.close()
            if self.state_manager:
                self.state_manager.update_system_health(database_connected=False)

        # Close Redis connection
        if self.cache:
            await self.cache.close()
            if self.state_manager:
                self.state_manager.update_system_health(redis_connected=False)

        logger.info("✅ Shutdown complete")


async def main():
    """Main entry point"""
    bot = AdvancedArbitrageBot()

    # Setup signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(bot.shutdown()))

    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
