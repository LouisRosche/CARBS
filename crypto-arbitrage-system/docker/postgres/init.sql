-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Price tracking with TimescaleDB hypertable
CREATE TABLE prices (
    timestamp TIMESTAMPTZ NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    bid NUMERIC(20,8) NOT NULL,
    ask NUMERIC(20,8) NOT NULL,
    bid_volume NUMERIC(20,8),
    ask_volume NUMERIC(20,8),
    spread_bps NUMERIC(10,4),  -- Spread in basis points
    PRIMARY KEY (timestamp, exchange, symbol)
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('prices', 'timestamp');

-- Indexes for efficient querying
CREATE INDEX idx_prices_exchange_symbol_time ON prices (exchange, symbol, timestamp DESC);
CREATE INDEX idx_prices_symbol_time ON prices (symbol, timestamp DESC);

-- Enable compression (reduces storage by ~90%)
ALTER TABLE prices SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'exchange,symbol',
    timescaledb.compress_orderby = 'timestamp DESC'
);

-- Auto-compress data older than 7 days
SELECT add_compression_policy('prices', INTERVAL '7 days');

-- Arbitrage opportunities detected
CREATE TABLE opportunities (
    id SERIAL PRIMARY KEY,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    buy_exchange VARCHAR(20) NOT NULL,
    sell_exchange VARCHAR(20) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    buy_price NUMERIC(20,8) NOT NULL,
    sell_price NUMERIC(20,8) NOT NULL,
    spread_percent NUMERIC(5,3) NOT NULL,
    spread_bps NUMERIC(10,4) NOT NULL,
    potential_profit_usd NUMERIC(20,8),
    estimated_profit_after_fees NUMERIC(20,8),
    buy_fee_percent NUMERIC(5,4),
    sell_fee_percent NUMERIC(5,4),
    slippage_estimate NUMERIC(5,4),
    executed BOOLEAN DEFAULT FALSE,
    execution_id INTEGER
);

CREATE INDEX idx_opportunities_detected_at ON opportunities (detected_at DESC);
CREATE INDEX idx_opportunities_executed_spread ON opportunities (executed, spread_percent DESC);
CREATE INDEX idx_opportunities_symbol_time ON opportunities (symbol, detected_at DESC);

-- Trade executions
CREATE TABLE executions (
    id SERIAL PRIMARY KEY,
    opportunity_id INTEGER REFERENCES opportunities(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL, -- 'pending', 'completed', 'failed', 'partial', 'cancelled'
    execution_time_ms INTEGER,
    
    -- Buy side
    buy_exchange VARCHAR(20) NOT NULL,
    buy_order_id VARCHAR(100),
    buy_amount NUMERIC(20,8),
    buy_filled_amount NUMERIC(20,8),
    buy_avg_price NUMERIC(20,8),
    buy_fee NUMERIC(20,8),
    buy_fee_currency VARCHAR(10),
    buy_slippage_bps NUMERIC(10,4),
    
    -- Sell side
    sell_exchange VARCHAR(20) NOT NULL,
    sell_order_id VARCHAR(100),
    sell_amount NUMERIC(20,8),
    sell_filled_amount NUMERIC(20,8),
    sell_avg_price NUMERIC(20,8),
    sell_fee NUMERIC(20,8),
    sell_fee_currency VARCHAR(10),
    sell_slippage_bps NUMERIC(10,4),
    
    -- Results
    gross_profit_usd NUMERIC(20,8),
    net_profit_usd NUMERIC(20,8),
    profit_percent NUMERIC(5,3),
    roi_percent NUMERIC(6,3),
    
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);

CREATE INDEX idx_executions_started_at ON executions (started_at DESC);
CREATE INDEX idx_executions_status ON executions (status);
CREATE INDEX idx_executions_opportunity ON executions (opportunity_id);

-- Add foreign key after execution table exists
ALTER TABLE opportunities ADD CONSTRAINT fk_execution
    FOREIGN KEY (execution_id) REFERENCES executions(id);

-- Account balances (cached from exchanges)
CREATE TABLE balances (
    exchange VARCHAR(20) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    free NUMERIC(20,8) NOT NULL,
    locked NUMERIC(20,8) NOT NULL,
    total NUMERIC(20,8) GENERATED ALWAYS AS (free + locked) STORED,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (exchange, currency)
);

CREATE INDEX idx_balances_exchange ON balances (exchange);
CREATE INDEX idx_balances_updated_at ON balances (updated_at DESC);

-- Exchange metadata and fees
CREATE TABLE exchange_info (
    exchange VARCHAR(20) PRIMARY KEY,
    taker_fee_percent NUMERIC(5,4) NOT NULL,
    maker_fee_percent NUMERIC(5,4) NOT NULL,
    withdrawal_fee JSONB,  -- Fees per currency
    min_order_size JSONB,  -- Min sizes per symbol
    max_order_size JSONB,
    enabled BOOLEAN DEFAULT TRUE,
    last_health_check TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Configuration and risk parameters
CREATE TABLE config (
    key VARCHAR(50) PRIMARY KEY,
    value TEXT NOT NULL,
    value_type VARCHAR(20) DEFAULT 'string', -- 'string', 'number', 'boolean', 'json'
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by VARCHAR(50)
);

-- Insert default configuration
INSERT INTO config (key, value, value_type, description) VALUES 
    ('min_spread_percent', '0.3', 'number', 'Minimum spread to trigger opportunity'),
    ('max_position_size_usd', '500', 'number', 'Maximum position size in USD'),
    ('max_daily_trades', '20', 'number', 'Maximum trades per day'),
    ('max_daily_loss_usd', '100', 'number', 'Maximum daily loss limit'),
    ('enabled_exchanges', '["binance", "coinbase", "kraken"]', 'json', 'Active exchanges'),
    ('enabled_symbols', '["BTC/USDT", "ETH/USDT"]', 'json', 'Monitored trading pairs'),
    ('paper_trading', 'true', 'boolean', 'Paper trading mode enabled'),
    ('order_timeout_seconds', '30', 'number', 'Order timeout duration'),
    ('max_slippage_bps', '50', 'number', 'Maximum acceptable slippage in basis points'),
    ('telegram_alerts', 'true', 'boolean', 'Enable Telegram notifications'),
    ('risk_limit_enabled', 'true', 'boolean', 'Enable risk management checks');

-- System logs and events
CREATE TABLE system_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    level VARCHAR(10) NOT NULL, -- 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    component VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB,
    error_trace TEXT
);

CREATE INDEX idx_system_logs_timestamp ON system_logs (timestamp DESC);
CREATE INDEX idx_system_logs_level ON system_logs (level);

-- Performance metrics
CREATE TABLE performance_metrics (
    timestamp TIMESTAMPTZ NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    metric_value NUMERIC(20,8) NOT NULL,
    exchange VARCHAR(20),
    symbol VARCHAR(20),
    metadata JSONB
);

SELECT create_hypertable('performance_metrics', 'timestamp');
CREATE INDEX idx_performance_metrics ON performance_metrics (metric_name, timestamp DESC);

-- Continuous aggregates for analytics
CREATE MATERIALIZED VIEW opportunity_stats_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', detected_at) AS hour,
    symbol,
    COUNT(*) as count,
    AVG(spread_percent) as avg_spread,
    MAX(spread_percent) as max_spread,
    AVG(estimated_profit_after_fees) as avg_profit,
    COUNT(CASE WHEN executed THEN 1 END) as executed_count
FROM opportunities
GROUP BY hour, symbol
WITH NO DATA;

-- Refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('opportunity_stats_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- View for symbol performance
CREATE VIEW symbol_performance AS
SELECT
    symbol,
    COUNT(*) as total_opportunities,
    AVG(spread_percent) as avg_spread,
    MAX(spread_percent) as max_spread,
    AVG(estimated_profit_after_fees) as avg_profit,
    COUNT(CASE WHEN executed THEN 1 END) as executed_count,
    MAX(detected_at) as last_opportunity
FROM opportunities
GROUP BY symbol
ORDER BY total_opportunities DESC;

-- View for exchange pair performance
CREATE VIEW exchange_pair_performance AS
SELECT
    buy_exchange,
    sell_exchange,
    symbol,
    COUNT(*) as opportunities,
    AVG(spread_percent) as avg_spread,
    AVG(estimated_profit_after_fees) as avg_profit
FROM opportunities
WHERE detected_at > NOW() - INTERVAL '7 days'
GROUP BY buy_exchange, sell_exchange, symbol
HAVING COUNT(*) > 10
ORDER BY avg_spread DESC;

-- Data retention policies
SELECT add_retention_policy('prices', INTERVAL '90 days');
SELECT add_retention_policy('performance_metrics', INTERVAL '90 days');

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO arbitrage_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO arbitrage_user;
