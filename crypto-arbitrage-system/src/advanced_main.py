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
import logging
import signal
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timezone

import ccxt.pro as ccxtpro

from core.advanced_engine import (
    AdvancedArbitrageEngine,
    EnhancedOrderBook,
    OpportunityScore
)
from core.execution_engine import ExecutionEngine, TradeRecord as ExecTradeRecord
from core.risk_manager import RiskManager, TradeRecord
from core.state_manager import StateManager, get_state_manager
from database.connection import DatabasePool
from utils.cache import RedisCache
from utils.metrics import MetricsCollector
from config.settings import load_config, ConfigLoadError, ConfigValidationError

# Import optional modules with graceful fallbacks
try:
    from core.antifragile import AntifragileCore
    ANTIFRAGILE_AVAILABLE = True
except ImportError:
    ANTIFRAGILE_AVAILABLE = False

try:
    from signals import SignalManager, SentimentAggregator
    SIGNALS_AVAILABLE = True
except ImportError:
    SIGNALS_AVAILABLE = False

try:
    from ml import MLAnalyzer
    ML_ANALYZER_AVAILABLE = True
except ImportError:
    ML_ANALYZER_AVAILABLE = False

try:
    from notifications import NotificationManager
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False

try:
    from compliance import ComplianceManager
    COMPLIANCE_AVAILABLE = True
except ImportError:
    COMPLIANCE_AVAILABLE = False

# Ensure log directory exists
log_dir = Path('data/logs')
log_dir.mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / 'arbitrage.log')
    ]
)

logger = logging.getLogger(__name__)


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
        self.state_manager = None

        # Optional integrated modules
        self.antifragile = None
        self.signal_manager = None
        self.sentiment_aggregator = None
        self.ml_analyzer = None
        self.notification_manager = None
        self.compliance_manager = None

        self.running = False
        self.shutdown_event = asyncio.Event()

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

        # Initialize advanced components
        self.advanced_engine = AdvancedArbitrageEngine(self.config)
        self.execution_engine = ExecutionEngine(self.config, self.exchanges)
        self.risk_manager = RiskManager(self.config)

        # Initialize optional integrated modules
        await self._initialize_optional_modules()

        logger.info(f"✅ Initialized {len(self.exchanges)} exchanges")
        logger.info(f"📊 Monitoring: {', '.join(self.config.symbols)}")
        logger.info(f"🎯 Min spread: {self.config.trading.min_spread_percent}%")
        logger.info(f"📝 Mode: {'PAPER TRADING' if self.config.trading.mode == 'paper' else 'LIVE TRADING'}")

        features = ["ML Scoring", "Risk Management", "Circuit Breakers"]
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

    async def fetch_orderbook(self, exchange_name: str, symbol: str) -> EnhancedOrderBook:
        """Fetch enhanced orderbook"""
        cache_key = f"ob:{exchange_name}:{symbol}"

        # Check cache
        cached = await self.cache.get(cache_key)
        if cached:
            self.metrics.increment('orderbook_cache_hits')
            # Reconstruct Decimal and datetime from cached strings
            return EnhancedOrderBook(
                exchange=cached['exchange'],
                symbol=cached['symbol'],
                timestamp=datetime.fromisoformat(cached['timestamp']),
                bids=[(Decimal(p), Decimal(v)) for p, v in cached['bids']],
                asks=[(Decimal(p), Decimal(v)) for p, v in cached['asks']]
            )

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

            # Update price history for cointegration analysis
            mid_price = orderbook.mid_price
            self.advanced_engine.update_price_history(
                exchange_name, symbol, mid_price, orderbook.timestamp
            )

            # Cache for 1 second
            await self.cache.set(cache_key, orderbook.__dict__, ttl=1)

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

        # Filter valid orderbooks
        valid_orderbooks = [
            ob for ob in orderbooks
            if isinstance(ob, EnhancedOrderBook) and ob is not None
        ]

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
            amount=amount
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
                successful_trades=portfolio_risk.winning_trades if hasattr(portfolio_risk, 'winning_trades') else 0
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

            # Record in compliance if available
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
                    logger.warning(f"Compliance recording failed: {e}")

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
                # Insert opportunity
                opp_id = await conn.fetchval("""
                    INSERT INTO opportunities
                    (detected_at, buy_exchange, sell_exchange, symbol,
                     buy_price, sell_price, spread_percent, spread_bps,
                     potential_profit_usd, estimated_profit_after_fees,
                     buy_fee_percent, sell_fee_percent, slippage_estimate, executed)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    RETURNING id
                """,
                    datetime.now(timezone.utc),
                    opportunity['buy_exchange'],
                    opportunity['sell_exchange'],
                    opportunity['symbol'],
                    float(opportunity['buy_price']),
                    float(opportunity['sell_price']),
                    float(opportunity['spread_percent']),
                    float(opportunity['spread_percent'] * 100),
                    float(opportunity['position_size'] * opportunity['net_spread']),
                    float(result.net_profit),
                    float(opportunity['buy_fee'] * 100),
                    float(opportunity['sell_fee'] * 100),
                    float((opportunity['buy_slippage'] + opportunity['sell_slippage']) * 100),
                    True
                )

                # Insert execution
                await conn.execute("""
                    INSERT INTO executions
                    (opportunity_id, started_at, completed_at, status, execution_time_ms,
                     buy_exchange, buy_filled_amount, buy_avg_price, buy_fee,
                     sell_exchange, sell_filled_amount, sell_avg_price, sell_fee,
                     gross_profit_usd, net_profit_usd, profit_percent)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                """,
                    opp_id,
                    result.buy_order.created_at,
                    result.buy_order.updated_at,
                    'completed',
                    result.execution_time_ms,
                    opportunity['buy_exchange'],
                    float(result.buy_order.filled_amount),
                    float(result.buy_order.avg_fill_price),
                    float(result.buy_order.fee),
                    opportunity['sell_exchange'],
                    float(result.sell_order.filled_amount),
                    float(result.sell_order.avg_fill_price),
                    float(result.sell_order.fee),
                    float(result.gross_profit),
                    float(result.net_profit),
                    float(opportunity['spread_percent'])
                )

        except Exception as e:
            logger.error(f"Failed to save execution to database: {e}")

    async def monitor_symbol(self, symbol: str):
        """Continuously monitor one symbol"""
        logger.info(f"👀 Monitoring {symbol}...")

        check_interval = self.config.performance.get('check_interval_seconds', 1)

        while self.running:
            try:
                # Find and score opportunities
                opportunity = await self.find_and_score_arbitrage(symbol)

                if opportunity:
                    # Execute if passes all checks
                    await self.execute_opportunity(opportunity)

                await asyncio.sleep(check_interval)

            except Exception as e:
                logger.error(f"Error monitoring {symbol}: {e}", exc_info=True)
                await asyncio.sleep(check_interval * 2)

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

        # Monitor all symbols in parallel
        tasks = [
            self.monitor_symbol(symbol)
            for symbol in self.config.symbols
        ]

        # Add stats printer
        tasks.append(self.print_stats())

        # Add sentiment monitoring if signal module available
        if self.signal_manager and self.sentiment_aggregator:
            tasks.append(self._monitor_sentiment())

        # Add antifragile adaptation if available
        if self.antifragile:
            tasks.append(self._run_antifragile_adaptation())

        await asyncio.gather(*tasks, return_exceptions=True)

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
                    logger.info(f"🔄 Antifragile adaptations applied: {adaptations}")

                    # Update config with new parameters
                    for param, value in adaptations.items():
                        if hasattr(self.config.trading, param):
                            setattr(self.config.trading, param, value)

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
