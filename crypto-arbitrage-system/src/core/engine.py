"""
Core Arbitrage Engine

Implements async-optimized arbitrage detection based on:
- Beazley (2019): Asyncio performance patterns
- Harris (2003): Market microstructure and transaction costs
- Pole (2007): Statistical arbitrage methodology
"""

import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

import ccxt.pro as ccxtpro

from database.connection import DatabasePool
from utils.cache import RedisCache
from utils.metrics import MetricsCollector
from config.settings import Config

logger = logging.getLogger(__name__)


@dataclass
class Opportunity:
    """Arbitrage opportunity data structure"""
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: Decimal
    sell_price: Decimal
    spread_percent: Decimal
    spread_bps: Decimal
    estimated_profit_usd: Decimal
    estimated_profit_after_fees: Decimal
    buy_fee_percent: Decimal
    sell_fee_percent: Decimal
    slippage_estimate: Decimal
    detected_at: datetime
    confidence_score: float = 0.0


@dataclass
class OrderBook:
    """Orderbook snapshot"""
    exchange: str
    symbol: str
    timestamp: datetime
    bids: List[Tuple[Decimal, Decimal]]  # [(price, volume), ...]
    asks: List[Tuple[Decimal, Decimal]]

    @property
    def best_bid(self) -> Tuple[Decimal, Decimal]:
        return self.bids[0] if self.bids else (Decimal('0'), Decimal('0'))

    @property
    def best_ask(self) -> Tuple[Decimal, Decimal]:
        return self.asks[0] if self.asks else (Decimal('0'), Decimal('0'))

    def estimate_slippage(self, side: str, position_size_usd: Decimal) -> Decimal:
        """
        Estimate slippage based on orderbook depth for a given position size.

        Args:
            side: 'buy' or 'sell'
            position_size_usd: Size of the position in USD

        Returns:
            Estimated slippage as a decimal (e.g., 0.001 = 0.1%)
        """
        if position_size_usd <= 0:
            return Decimal('0')

        orders = self.asks if side == 'buy' else self.bids

        if not orders:
            return Decimal('0.005')  # Default 50 bps if no orderbook

        best_price = orders[0][0]
        if best_price <= 0:
            return Decimal('0.005')

        # Calculate volume-weighted average price for the position
        remaining_usd = position_size_usd
        total_value = Decimal('0')
        total_qty = Decimal('0')

        for price, qty in orders:
            level_value_usd = price * qty
            if remaining_usd <= level_value_usd:
                # Partial fill at this level
                fill_qty = remaining_usd / price
                total_value += fill_qty * price
                total_qty += fill_qty
                break
            else:
                # Full fill at this level
                total_value += level_value_usd
                total_qty += qty
                remaining_usd -= level_value_usd

        if total_qty == 0:
            return Decimal('0.005')  # Default 50 bps

        vwap = total_value / total_qty

        # Slippage is the difference between VWAP and best price
        if side == 'buy':
            slippage = (vwap - best_price) / best_price
        else:
            slippage = (best_price - vwap) / best_price

        # Ensure non-negative and cap at reasonable maximum
        slippage = max(Decimal('0'), slippage)
        slippage = min(slippage, Decimal('0.02'))  # Cap at 2%

        return slippage


class ArbitrageEngine:
    """
    High-performance arbitrage detection engine
    
    Uses async/await for concurrent exchange monitoring and
    implements transaction-cost adjusted spread calculation.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.exchanges: Dict[str, ccxtpro.Exchange] = {}
        self.db_pool: Optional[DatabasePool] = None
        self.cache: Optional[RedisCache] = None
        self.metrics: Optional[MetricsCollector] = None
        self.running = False
        
        # Risk parameters
        self.min_spread = Decimal(str(config.trading.min_spread_percent)) / 100
        self.max_spread = Decimal(str(config.trading.max_spread_percent)) / 100
        self.max_position_usd = Decimal(str(config.trading.max_position_usd))
        
        # Performance tracking
        self.opportunities_found = 0
        self.orderbooks_processed = 0
        
    async def initialize(self):
        """Initialize all connections and resources"""
        logger.info("🚀 Initializing Arbitrage Engine...")
        
        # Initialize database pool
        self.db_pool = DatabasePool(self.config.database)
        await self.db_pool.connect()
        
        # Initialize Redis cache
        self.cache = RedisCache(self.config.redis)
        await self.cache.connect()
        
        # Initialize metrics collector
        self.metrics = MetricsCollector(self.config.monitoring['prometheus_port'])
        
        # Initialize exchanges
        await self._initialize_exchanges()
        
        # Load exchange fee structures
        await self._load_exchange_fees()
        
        logger.info(f"✅ Initialized {len(self.exchanges)} exchanges")
        logger.info(f"📊 Monitoring: {', '.join(self.config.symbols)}")
        logger.info(f"🎯 Min spread: {self.min_spread*100:.2f}%")
        logger.info(f"📝 Mode: {'PAPER TRADING' if self.config.trading.mode == 'paper' else 'LIVE TRADING'}")
        
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
                
    async def _load_exchange_fees(self):
        """Load and cache exchange fee structures"""
        for exchange_name, exchange in self.exchanges.items():
            try:
                # Get fee structure from exchange
                fees = exchange.fees
                
                # Store in database
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO exchange_info (exchange, taker_fee_percent, maker_fee_percent)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (exchange) 
                        DO UPDATE SET 
                            taker_fee_percent = EXCLUDED.taker_fee_percent,
                            maker_fee_percent = EXCLUDED.maker_fee_percent,
                            updated_at = NOW()
                    """, exchange_name, 
                    float(fees['trading']['taker']), 
                    float(fees['trading']['maker']))
                    
            except Exception as e:
                logger.warning(f"Could not load fees for {exchange_name}: {e}")
    
    async def fetch_orderbook(self, exchange_name: str, symbol: str) -> Optional[OrderBook]:
        """
        Fetch orderbook with caching and error handling
        
        Uses 1-second cache TTL to balance freshness vs API load
        """
        cache_key = f"ob:{exchange_name}:{symbol}"
        
        # Check cache
        cached = await self.cache.get(cache_key)
        if cached:
            self.metrics.increment('orderbook_cache_hits')
            return OrderBook(**cached)
        
        try:
            exchange = self.exchanges[exchange_name]
            ob_data = await exchange.watch_order_book(symbol)
            
            orderbook = OrderBook(
                exchange=exchange_name,
                symbol=symbol,
                timestamp=datetime.now(timezone.utc),
                bids=[(Decimal(str(p)), Decimal(str(v))) for p, v in ob_data['bids'][:10]],
                asks=[(Decimal(str(p)), Decimal(str(v))) for p, v in ob_data['asks'][:10]]
            )
            
            # Cache for 1 second
            await self.cache.set(cache_key, orderbook.__dict__, ttl=1)
            
            self.metrics.increment('orderbooks_fetched')
            self.orderbooks_processed += 1
            
            return orderbook
            
        except Exception as e:
            logger.error(f"Error fetching {exchange_name} {symbol} orderbook: {e}")
            self.metrics.increment('orderbook_errors')
            return None
    
    def calculate_spread(
        self,
        buy_ob: OrderBook,
        sell_ob: OrderBook,
        position_size_usd: Decimal
    ) -> Optional[Opportunity]:
        """
        Calculate transaction-cost adjusted spread

        Incorporates:
        - Trading fees (taker assumed for speed)
        - Dynamic slippage estimation based on orderbook depth
        - Minimum profitability threshold
        """
        # Get best prices
        buy_price, buy_volume = buy_ob.best_ask
        sell_price, sell_volume = sell_ob.best_bid

        if buy_price == 0 or sell_price == 0:
            return None

        # Calculate gross spread
        gross_spread = (sell_price - buy_price) / buy_price
        spread_percent = gross_spread * 100
        spread_bps = gross_spread * 10000

        # Get exchange fees
        buy_fee = Decimal(str(self.config.exchanges[buy_ob.exchange].get('taker_fee', 0.001)))
        sell_fee = Decimal(str(self.config.exchanges[sell_ob.exchange].get('taker_fee', 0.001)))

        # Dynamic slippage estimation based on orderbook depth
        buy_slippage = buy_ob.estimate_slippage('buy', position_size_usd)
        sell_slippage = sell_ob.estimate_slippage('sell', position_size_usd)
        estimated_slippage = buy_slippage + sell_slippage

        # Calculate net spread after costs
        net_spread = gross_spread - buy_fee - sell_fee - estimated_slippage

        # Check minimum profitability
        if net_spread < self.min_spread:
            return None

        # Reject suspiciously high spreads (likely stale data)
        if gross_spread > self.max_spread:
            logger.warning(f"Rejecting suspicious spread: {spread_percent:.2f}%")
            return None

        # Calculate estimated profit
        estimated_profit = position_size_usd * net_spread

        # Calculate confidence score based on liquidity and spread stability
        confidence_score = self._calculate_confidence(buy_ob, sell_ob, position_size_usd)

        opportunity = Opportunity(
            symbol=buy_ob.symbol,
            buy_exchange=buy_ob.exchange,
            sell_exchange=sell_ob.exchange,
            buy_price=buy_price,
            sell_price=sell_price,
            spread_percent=spread_percent,
            spread_bps=spread_bps,
            estimated_profit_usd=estimated_profit,
            estimated_profit_after_fees=estimated_profit,
            buy_fee_percent=buy_fee * 100,
            sell_fee_percent=sell_fee * 100,
            slippage_estimate=estimated_slippage * 100,
            detected_at=datetime.now(timezone.utc),
            confidence_score=confidence_score
        )

        return opportunity

    def _calculate_confidence(
        self,
        buy_ob: OrderBook,
        sell_ob: OrderBook,
        position_size_usd: Decimal
    ) -> float:
        """
        Calculate confidence score for an arbitrage opportunity.

        Based on:
        - Orderbook depth (liquidity)
        - Spread size relative to slippage
        - Number of price levels available

        Returns:
            Confidence score between 0 and 1
        """
        try:
            # Liquidity score (0-0.4): Based on available volume at best prices
            buy_volume_usd = buy_ob.best_ask[0] * buy_ob.best_ask[1]
            sell_volume_usd = sell_ob.best_bid[0] * sell_ob.best_bid[1]
            min_volume = min(float(buy_volume_usd), float(sell_volume_usd))
            liquidity_ratio = min(min_volume / float(position_size_usd), 5.0) / 5.0
            liquidity_score = liquidity_ratio * 0.4

            # Depth score (0-0.3): Based on number of price levels
            buy_depth = min(len(buy_ob.asks), 10) / 10.0
            sell_depth = min(len(sell_ob.bids), 10) / 10.0
            depth_score = ((buy_depth + sell_depth) / 2) * 0.3

            # Slippage score (0-0.3): Lower slippage = higher confidence
            total_slippage = float(buy_ob.estimate_slippage('buy', position_size_usd) +
                                   sell_ob.estimate_slippage('sell', position_size_usd))
            slippage_score = max(0, 1 - total_slippage * 100) * 0.3

            return min(liquidity_score + depth_score + slippage_score, 1.0)
        except Exception:
            return 0.5  # Default moderate confidence
    
    async def find_arbitrage(self, symbol: str) -> Optional[Opportunity]:
        """
        Find best arbitrage opportunity for symbol
        
        Fetches orderbooks concurrently and compares all exchange pairs
        """
        # Fetch all orderbooks concurrently
        tasks = [
            self.fetch_orderbook(ex_name, symbol)
            for ex_name in self.exchanges.keys()
        ]
        orderbooks = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful fetches
        valid_orderbooks = [
            ob for ob in orderbooks 
            if isinstance(ob, OrderBook)
        ]
        
        if len(valid_orderbooks) < 2:
            return None
        
        # Find best opportunity across all pairs
        best_opportunity = None
        max_spread = Decimal('0')
        
        for buy_ob in valid_orderbooks:
            for sell_ob in valid_orderbooks:
                if buy_ob.exchange == sell_ob.exchange:
                    continue
                
                opportunity = self.calculate_spread(
                    buy_ob, 
                    sell_ob, 
                    self.max_position_usd
                )
                
                if opportunity and opportunity.spread_percent > max_spread:
                    max_spread = opportunity.spread_percent
                    best_opportunity = opportunity
        
        return best_opportunity
    
    async def save_opportunity(self, opp: Opportunity):
        """Persist opportunity to database"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO opportunities 
                    (detected_at, buy_exchange, sell_exchange, symbol, 
                     buy_price, sell_price, spread_percent, spread_bps,
                     potential_profit_usd, estimated_profit_after_fees,
                     buy_fee_percent, sell_fee_percent, slippage_estimate)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                    opp.detected_at, opp.buy_exchange, opp.sell_exchange, opp.symbol,
                    float(opp.buy_price), float(opp.sell_price), 
                    float(opp.spread_percent), float(opp.spread_bps),
                    float(opp.estimated_profit_usd), float(opp.estimated_profit_after_fees),
                    float(opp.buy_fee_percent), float(opp.sell_fee_percent),
                    float(opp.slippage_estimate)
                )
                
            self.opportunities_found += 1
            self.metrics.increment('opportunities_found')
            
        except Exception as e:
            logger.error(f"Failed to save opportunity: {e}")
    
    async def monitor_symbol(self, symbol: str):
        """Continuously monitor one symbol"""
        logger.info(f"👀 Monitoring {symbol}...")
        
        check_interval = self.config.performance.get('check_interval_seconds', 1)
        
        while self.running:
            try:
                opp = await self.find_arbitrage(symbol)
                
                if opp:
                    await self.save_opportunity(opp)
                    logger.info(
                        f"✨ {opp.symbol}: {opp.spread_percent:.3f}% | "
                        f"Buy {opp.buy_exchange} @ ${opp.buy_price:.2f} | "
                        f"Sell {opp.sell_exchange} @ ${opp.sell_price:.2f} | "
                        f"Profit: ${opp.estimated_profit_after_fees:.2f}"
                    )
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error monitoring {symbol}: {e}")
                await asyncio.sleep(check_interval * 2)
    
    async def run(self):
        """Main execution loop"""
        self.running = True
        await self.initialize()
        
        # Monitor all symbols in parallel
        tasks = [
            self.monitor_symbol(symbol) 
            for symbol in self.config.symbols
        ]
        
        await asyncio.gather(*tasks)
    
    async def shutdown(self):
        """Cleanup and close connections"""
        logger.info("🛑 Shutting down...")
        self.running = False
        
        # Close exchange connections
        for exchange in self.exchanges.values():
            await exchange.close()
        
        # Close database pool
        if self.db_pool:
            await self.db_pool.close()
        
        # Close Redis connection
        if self.cache:
            await self.cache.close()
        
        logger.info(f"📊 Final stats: {self.opportunities_found} opportunities found, "
                   f"{self.orderbooks_processed} orderbooks processed")
