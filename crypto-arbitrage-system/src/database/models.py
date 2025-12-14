"""
Database Models and Repository Pattern

Production-grade database layer with:
- SQLAlchemy-style models (using asyncpg)
- Repository pattern for data access
- Trade history tracking
- Position management
- Balance snapshots
- Audit trail
- Performance analytics

Schema optimized for:
- High-frequency inserts
- Time-series queries
- Portfolio aggregations
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)


# SQL Schema definitions
SCHEMA_SQL = """
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Enum types
DO $$ BEGIN
    CREATE TYPE order_side AS ENUM ('buy', 'sell');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE order_type AS ENUM ('market', 'limit', 'stop_loss', 'stop_limit');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE order_status AS ENUM ('pending', 'submitted', 'partially_filled', 'filled', 'cancelled', 'failed', 'expired');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE trade_type AS ENUM ('arbitrage', 'rebalance', 'manual', 'emergency_close');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Trades table (core trading history)
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id VARCHAR(100),
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side order_side NOT NULL,
    order_type order_type NOT NULL,
    status order_status NOT NULL DEFAULT 'pending',
    trade_type trade_type NOT NULL DEFAULT 'arbitrage',

    -- Pricing
    requested_price DECIMAL(24, 8) NOT NULL,
    executed_price DECIMAL(24, 8),
    slippage_bps DECIMAL(10, 4),

    -- Quantities
    requested_quantity DECIMAL(24, 8) NOT NULL,
    filled_quantity DECIMAL(24, 8) DEFAULT 0,

    -- Fees
    fee DECIMAL(24, 8) DEFAULT 0,
    fee_currency VARCHAR(10),

    -- Profit/Loss
    gross_pnl DECIMAL(24, 8),
    net_pnl DECIMAL(24, 8),

    -- Execution metrics
    execution_time_ms INTEGER,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    filled_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Metadata
    client_order_id VARCHAR(100),
    notes TEXT,
    metadata JSONB DEFAULT '{}',

    -- Indexing helpers
    trade_date DATE GENERATED ALWAYS AS (DATE(created_at)) STORED
);

-- Arbitrage executions (links two legs of arbitrage trade)
CREATE TABLE IF NOT EXISTS arbitrage_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    buy_trade_id UUID REFERENCES trades(id),
    sell_trade_id UUID REFERENCES trades(id),
    symbol VARCHAR(20) NOT NULL,

    -- Exchanges
    buy_exchange VARCHAR(50) NOT NULL,
    sell_exchange VARCHAR(50) NOT NULL,

    -- Pricing
    buy_price DECIMAL(24, 8) NOT NULL,
    sell_price DECIMAL(24, 8) NOT NULL,
    spread_bps DECIMAL(10, 4) NOT NULL,

    -- Quantities
    quantity DECIMAL(24, 8) NOT NULL,

    -- Results
    gross_profit DECIMAL(24, 8),
    total_fees DECIMAL(24, 8),
    net_profit DECIMAL(24, 8),

    -- Success tracking
    success BOOLEAN NOT NULL DEFAULT false,
    error_message TEXT,

    -- Execution metrics
    total_execution_time_ms INTEGER,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    -- Metadata
    opportunity_id VARCHAR(100),
    metadata JSONB DEFAULT '{}'
);

-- Positions (current holdings per exchange)
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,

    -- Position data
    quantity DECIMAL(24, 8) NOT NULL DEFAULT 0,
    avg_entry_price DECIMAL(24, 8),
    current_price DECIMAL(24, 8),

    -- Calculated fields
    unrealized_pnl DECIMAL(24, 8),
    realized_pnl DECIMAL(24, 8) DEFAULT 0,

    -- Risk metrics
    cost_basis DECIMAL(24, 8),
    market_value DECIMAL(24, 8),

    -- Timestamps
    opened_at TIMESTAMPTZ,
    last_trade_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    UNIQUE(exchange, symbol)
);

-- Balance snapshots (point-in-time balance records)
CREATE TABLE IF NOT EXISTS balance_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exchange VARCHAR(50) NOT NULL,
    currency VARCHAR(10) NOT NULL,

    -- Balances
    total DECIMAL(24, 8) NOT NULL,
    available DECIMAL(24, 8) NOT NULL,
    locked DECIMAL(24, 8) DEFAULT 0,

    -- USD equivalent
    usd_value DECIMAL(24, 8),

    -- Timestamp
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Partitioning helper
    snapshot_date DATE GENERATED ALWAYS AS (DATE(snapshot_at)) STORED
);

-- Daily PnL summary (aggregated daily performance)
CREATE TABLE IF NOT EXISTS daily_pnl (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trade_date DATE NOT NULL,
    exchange VARCHAR(50),

    -- Trade counts
    total_trades INTEGER DEFAULT 0,
    successful_trades INTEGER DEFAULT 0,
    failed_trades INTEGER DEFAULT 0,

    -- PnL
    gross_pnl DECIMAL(24, 8) DEFAULT 0,
    total_fees DECIMAL(24, 8) DEFAULT 0,
    net_pnl DECIMAL(24, 8) DEFAULT 0,

    -- Metrics
    win_rate DECIMAL(5, 4),
    avg_trade_size DECIMAL(24, 8),
    total_volume DECIMAL(24, 8),

    -- Best/Worst
    best_trade_pnl DECIMAL(24, 8),
    worst_trade_pnl DECIMAL(24, 8),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(trade_date, exchange)
);

-- Opportunities (arbitrage opportunities found)
CREATE TABLE IF NOT EXISTS opportunities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,

    -- Exchanges
    buy_exchange VARCHAR(50) NOT NULL,
    sell_exchange VARCHAR(50) NOT NULL,

    -- Prices
    buy_price DECIMAL(24, 8) NOT NULL,
    sell_price DECIMAL(24, 8) NOT NULL,
    spread_bps DECIMAL(10, 4) NOT NULL,

    -- Available liquidity
    available_quantity DECIMAL(24, 8),

    -- Scoring
    score DECIMAL(10, 4),
    confidence DECIMAL(5, 4),

    -- Status
    executed BOOLEAN DEFAULT false,
    execution_id UUID REFERENCES arbitrage_executions(id),
    skip_reason VARCHAR(100),

    -- Timestamps
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,

    -- Metadata
    metadata JSONB DEFAULT '{}'
);

-- Audit log (system events)
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'info',

    -- Actor
    user_id VARCHAR(100),
    ip_address INET,

    -- Event data
    message TEXT NOT NULL,
    details JSONB DEFAULT '{}',

    -- Resource
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),

    -- Timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_trades_exchange_symbol ON trades(exchange, symbol);
CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_trade_date ON trades(trade_date);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);

CREATE INDEX IF NOT EXISTS idx_arbitrage_created_at ON arbitrage_executions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_arbitrage_symbol ON arbitrage_executions(symbol);
CREATE INDEX IF NOT EXISTS idx_arbitrage_success ON arbitrage_executions(success);

CREATE INDEX IF NOT EXISTS idx_positions_exchange ON positions(exchange);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);

CREATE INDEX IF NOT EXISTS idx_balance_snapshot_at ON balance_snapshots(snapshot_at DESC);
CREATE INDEX IF NOT EXISTS idx_balance_exchange ON balance_snapshots(exchange, currency);

CREATE INDEX IF NOT EXISTS idx_daily_pnl_date ON daily_pnl(trade_date DESC);

CREATE INDEX IF NOT EXISTS idx_opportunities_discovered ON opportunities(discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_opportunities_symbol ON opportunities(symbol);

CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log(event_type);

-- Update trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_trades_updated_at ON trades;
CREATE TRIGGER update_trades_updated_at
    BEFORE UPDATE ON trades
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_positions_updated_at ON positions;
CREATE TRIGGER update_positions_updated_at
    BEFORE UPDATE ON positions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
"""


# Data classes for models

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LIMIT = "stop_limit"


class OrderStatus(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"
    EXPIRED = "expired"


class TradeType(Enum):
    ARBITRAGE = "arbitrage"
    REBALANCE = "rebalance"
    MANUAL = "manual"
    EMERGENCY_CLOSE = "emergency_close"


@dataclass
class Trade:
    """Trade record"""
    id: str = None
    external_id: str = None
    exchange: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.LIMIT
    status: OrderStatus = OrderStatus.PENDING
    trade_type: TradeType = TradeType.ARBITRAGE

    requested_price: Decimal = Decimal("0")
    executed_price: Decimal = None
    slippage_bps: Decimal = None

    requested_quantity: Decimal = Decimal("0")
    filled_quantity: Decimal = Decimal("0")

    fee: Decimal = Decimal("0")
    fee_currency: str = ""

    gross_pnl: Decimal = None
    net_pnl: Decimal = None

    execution_time_ms: int = None

    created_at: datetime = None
    submitted_at: datetime = None
    filled_at: datetime = None
    updated_at: datetime = None

    client_order_id: str = None
    notes: str = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class ArbitrageExecution:
    """Arbitrage execution record"""
    id: str = None
    buy_trade_id: str = None
    sell_trade_id: str = None
    symbol: str = ""

    buy_exchange: str = ""
    sell_exchange: str = ""

    buy_price: Decimal = Decimal("0")
    sell_price: Decimal = Decimal("0")
    spread_bps: Decimal = Decimal("0")

    quantity: Decimal = Decimal("0")

    gross_profit: Decimal = None
    total_fees: Decimal = None
    net_profit: Decimal = None

    success: bool = False
    error_message: str = None

    total_execution_time_ms: int = None

    created_at: datetime = None
    completed_at: datetime = None

    opportunity_id: str = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class Position:
    """Position record"""
    id: str = None
    exchange: str = ""
    symbol: str = ""

    quantity: Decimal = Decimal("0")
    avg_entry_price: Decimal = None
    current_price: Decimal = None

    unrealized_pnl: Decimal = None
    realized_pnl: Decimal = Decimal("0")

    cost_basis: Decimal = None
    market_value: Decimal = None

    opened_at: datetime = None
    last_trade_at: datetime = None
    updated_at: datetime = None


@dataclass
class BalanceSnapshot:
    """Balance snapshot record"""
    id: str = None
    exchange: str = ""
    currency: str = ""

    total: Decimal = Decimal("0")
    available: Decimal = Decimal("0")
    locked: Decimal = Decimal("0")

    usd_value: Decimal = None

    snapshot_at: datetime = None


@dataclass
class DailyPnL:
    """Daily P&L record"""
    id: str = None
    trade_date: datetime = None
    exchange: str = None

    total_trades: int = 0
    successful_trades: int = 0
    failed_trades: int = 0

    gross_pnl: Decimal = Decimal("0")
    total_fees: Decimal = Decimal("0")
    net_pnl: Decimal = Decimal("0")

    win_rate: Decimal = None
    avg_trade_size: Decimal = None
    total_volume: Decimal = None

    best_trade_pnl: Decimal = None
    worst_trade_pnl: Decimal = None


# Repository classes

class TradeRepository:
    """Repository for trade operations"""

    def __init__(self, pool):
        self.pool = pool

    async def create(self, trade: Trade) -> str:
        """Insert a new trade"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO trades (
                    external_id, exchange, symbol, side, order_type, status, trade_type,
                    requested_price, executed_price, slippage_bps,
                    requested_quantity, filled_quantity,
                    fee, fee_currency, gross_pnl, net_pnl,
                    execution_time_ms, submitted_at, filled_at,
                    client_order_id, notes, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22)
                RETURNING id
            """,
                trade.external_id, trade.exchange, trade.symbol,
                trade.side.value, trade.order_type.value, trade.status.value, trade.trade_type.value,
                trade.requested_price, trade.executed_price, trade.slippage_bps,
                trade.requested_quantity, trade.filled_quantity,
                trade.fee, trade.fee_currency, trade.gross_pnl, trade.net_pnl,
                trade.execution_time_ms, trade.submitted_at, trade.filled_at,
                trade.client_order_id, trade.notes, json.dumps(trade.metadata)
            )
            return str(row['id'])

    async def update_status(
        self,
        trade_id: str,
        status: OrderStatus,
        filled_quantity: Decimal = None,
        executed_price: Decimal = None,
        fee: Decimal = None
    ):
        """Update trade status"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE trades SET
                    status = $2,
                    filled_quantity = COALESCE($3, filled_quantity),
                    executed_price = COALESCE($4, executed_price),
                    fee = COALESCE($5, fee),
                    filled_at = CASE WHEN $2 = 'filled' THEN NOW() ELSE filled_at END
                WHERE id = $1
            """, trade_id, status.value, filled_quantity, executed_price, fee)

    async def get_by_id(self, trade_id: str) -> Optional[Trade]:
        """Get trade by ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM trades WHERE id = $1",
                trade_id
            )
            return self._row_to_trade(row) if row else None

    async def get_recent(
        self,
        exchange: str = None,
        symbol: str = None,
        limit: int = 100
    ) -> List[Trade]:
        """Get recent trades"""
        async with self.pool.acquire() as conn:
            query = "SELECT * FROM trades WHERE 1=1"
            params = []

            if exchange:
                params.append(exchange)
                query += f" AND exchange = ${len(params)}"

            if symbol:
                params.append(symbol)
                query += f" AND symbol = ${len(params)}"

            query += f" ORDER BY created_at DESC LIMIT {limit}"

            rows = await conn.fetch(query, *params)
            return [self._row_to_trade(row) for row in rows]

    async def get_daily_stats(
        self,
        date: datetime = None,
        exchange: str = None
    ) -> Dict:
        """Get daily trading statistics"""
        if date is None:
            date = datetime.now(timezone.utc).date()

        async with self.pool.acquire() as conn:
            query = """
                SELECT
                    COUNT(*) as total_trades,
                    COUNT(*) FILTER (WHERE status = 'filled') as successful_trades,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_trades,
                    SUM(gross_pnl) as gross_pnl,
                    SUM(fee) as total_fees,
                    SUM(net_pnl) as net_pnl,
                    AVG(filled_quantity * executed_price) as avg_trade_size,
                    SUM(filled_quantity * executed_price) as total_volume,
                    MAX(net_pnl) as best_trade,
                    MIN(net_pnl) as worst_trade
                FROM trades
                WHERE trade_date = $1
            """
            params = [date]

            if exchange:
                params.append(exchange)
                query = query.replace("WHERE", f"WHERE exchange = ${len(params)} AND")

            row = await conn.fetchrow(query, *params)
            return dict(row) if row else {}

    def _row_to_trade(self, row) -> Trade:
        """Convert database row to Trade object"""
        return Trade(
            id=str(row['id']),
            external_id=row['external_id'],
            exchange=row['exchange'],
            symbol=row['symbol'],
            side=OrderSide(row['side']),
            order_type=OrderType(row['order_type']),
            status=OrderStatus(row['status']),
            trade_type=TradeType(row['trade_type']),
            requested_price=row['requested_price'],
            executed_price=row['executed_price'],
            slippage_bps=row['slippage_bps'],
            requested_quantity=row['requested_quantity'],
            filled_quantity=row['filled_quantity'],
            fee=row['fee'],
            fee_currency=row['fee_currency'],
            gross_pnl=row['gross_pnl'],
            net_pnl=row['net_pnl'],
            execution_time_ms=row['execution_time_ms'],
            created_at=row['created_at'],
            submitted_at=row['submitted_at'],
            filled_at=row['filled_at'],
            updated_at=row['updated_at'],
            client_order_id=row['client_order_id'],
            notes=row['notes'],
            metadata=row['metadata'] or {}
        )


class ArbitrageRepository:
    """Repository for arbitrage execution operations"""

    def __init__(self, pool):
        self.pool = pool

    async def create(self, execution: ArbitrageExecution) -> str:
        """Insert a new arbitrage execution"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO arbitrage_executions (
                    buy_trade_id, sell_trade_id, symbol,
                    buy_exchange, sell_exchange,
                    buy_price, sell_price, spread_bps,
                    quantity, gross_profit, total_fees, net_profit,
                    success, error_message, total_execution_time_ms,
                    completed_at, opportunity_id, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                RETURNING id
            """,
                execution.buy_trade_id, execution.sell_trade_id, execution.symbol,
                execution.buy_exchange, execution.sell_exchange,
                execution.buy_price, execution.sell_price, execution.spread_bps,
                execution.quantity, execution.gross_profit, execution.total_fees, execution.net_profit,
                execution.success, execution.error_message, execution.total_execution_time_ms,
                execution.completed_at, execution.opportunity_id, json.dumps(execution.metadata)
            )
            return str(row['id'])

    async def get_performance_stats(
        self,
        days: int = 30
    ) -> Dict:
        """Get arbitrage performance statistics"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_executions,
                    COUNT(*) FILTER (WHERE success) as successful,
                    COUNT(*) FILTER (WHERE NOT success) as failed,
                    SUM(net_profit) FILTER (WHERE success) as total_profit,
                    AVG(net_profit) FILTER (WHERE success) as avg_profit,
                    AVG(spread_bps) as avg_spread_bps,
                    AVG(total_execution_time_ms) as avg_execution_time
                FROM arbitrage_executions
                WHERE created_at > NOW() - INTERVAL '%s days'
            """ % days)
            return dict(row) if row else {}


class PositionRepository:
    """Repository for position operations"""

    def __init__(self, pool):
        self.pool = pool

    async def upsert(self, position: Position):
        """Insert or update position"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO positions (
                    exchange, symbol, quantity, avg_entry_price, current_price,
                    unrealized_pnl, realized_pnl, cost_basis, market_value,
                    opened_at, last_trade_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (exchange, symbol) DO UPDATE SET
                    quantity = EXCLUDED.quantity,
                    avg_entry_price = EXCLUDED.avg_entry_price,
                    current_price = EXCLUDED.current_price,
                    unrealized_pnl = EXCLUDED.unrealized_pnl,
                    realized_pnl = positions.realized_pnl + COALESCE(EXCLUDED.realized_pnl, 0),
                    cost_basis = EXCLUDED.cost_basis,
                    market_value = EXCLUDED.market_value,
                    last_trade_at = EXCLUDED.last_trade_at
            """,
                position.exchange, position.symbol, position.quantity,
                position.avg_entry_price, position.current_price,
                position.unrealized_pnl, position.realized_pnl,
                position.cost_basis, position.market_value,
                position.opened_at, position.last_trade_at
            )

    async def get_all(self, exchange: str = None) -> List[Position]:
        """Get all positions"""
        async with self.pool.acquire() as conn:
            if exchange:
                rows = await conn.fetch(
                    "SELECT * FROM positions WHERE exchange = $1 AND quantity != 0",
                    exchange
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM positions WHERE quantity != 0"
                )
            return [self._row_to_position(row) for row in rows]

    async def get_total_value(self) -> Decimal:
        """Get total portfolio value"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COALESCE(SUM(market_value), 0) as total FROM positions"
            )
            return row['total']

    def _row_to_position(self, row) -> Position:
        return Position(
            id=str(row['id']),
            exchange=row['exchange'],
            symbol=row['symbol'],
            quantity=row['quantity'],
            avg_entry_price=row['avg_entry_price'],
            current_price=row['current_price'],
            unrealized_pnl=row['unrealized_pnl'],
            realized_pnl=row['realized_pnl'],
            cost_basis=row['cost_basis'],
            market_value=row['market_value'],
            opened_at=row['opened_at'],
            last_trade_at=row['last_trade_at'],
            updated_at=row['updated_at']
        )


class BalanceRepository:
    """Repository for balance operations"""

    def __init__(self, pool):
        self.pool = pool

    async def snapshot(self, balance: BalanceSnapshot):
        """Record a balance snapshot"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO balance_snapshots (
                    exchange, currency, total, available, locked, usd_value
                ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
                balance.exchange, balance.currency,
                balance.total, balance.available, balance.locked,
                balance.usd_value
            )

    async def get_latest(self, exchange: str, currency: str) -> Optional[BalanceSnapshot]:
        """Get latest balance snapshot"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM balance_snapshots
                WHERE exchange = $1 AND currency = $2
                ORDER BY snapshot_at DESC
                LIMIT 1
            """, exchange, currency)

            if row:
                return BalanceSnapshot(
                    id=str(row['id']),
                    exchange=row['exchange'],
                    currency=row['currency'],
                    total=row['total'],
                    available=row['available'],
                    locked=row['locked'],
                    usd_value=row['usd_value'],
                    snapshot_at=row['snapshot_at']
                )
            return None

    async def get_history(
        self,
        exchange: str,
        currency: str,
        days: int = 30
    ) -> List[BalanceSnapshot]:
        """Get balance history"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM balance_snapshots
                WHERE exchange = $1 AND currency = $2
                AND snapshot_at > NOW() - INTERVAL '%s days'
                ORDER BY snapshot_at DESC
            """ % days, exchange, currency)

            return [
                BalanceSnapshot(
                    id=str(row['id']),
                    exchange=row['exchange'],
                    currency=row['currency'],
                    total=row['total'],
                    available=row['available'],
                    locked=row['locked'],
                    usd_value=row['usd_value'],
                    snapshot_at=row['snapshot_at']
                )
                for row in rows
            ]


class DatabaseManager:
    """
    Central database manager

    Provides:
    - Schema migration
    - Connection pooling
    - Repository access
    """

    def __init__(self, pool):
        self.pool = pool
        self.trades = TradeRepository(pool)
        self.arbitrage = ArbitrageRepository(pool)
        self.positions = PositionRepository(pool)
        self.balances = BalanceRepository(pool)

    async def initialize_schema(self):
        """Create database schema"""
        async with self.pool.acquire() as conn:
            await conn.execute(SCHEMA_SQL)
            logger.info("Database schema initialized")

    async def health_check(self) -> bool:
        """Check database connectivity"""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


__all__ = [
    "SCHEMA_SQL",
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "TradeType",
    "Trade",
    "ArbitrageExecution",
    "Position",
    "BalanceSnapshot",
    "DailyPnL",
    "TradeRepository",
    "ArbitrageRepository",
    "PositionRepository",
    "BalanceRepository",
    "DatabaseManager"
]
