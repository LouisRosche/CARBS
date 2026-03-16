# CARBS - Crypto Arbitrage Bot System

Production-ready cryptocurrency arbitrage detection and execution platform.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## CRITICAL: RISK DISCLAIMER

**CRYPTOCURRENCY TRADING CARRIES SIGNIFICANT FINANCIAL RISK.**

- **This software is for EDUCATIONAL and RESEARCH purposes**
- **NOT financial advice** -- Consult qualified professionals before trading
- **You can LOSE ALL your capital** -- Never invest more than you can afford to lose
- **No profitability guarantees** -- Past performance does not indicate future results
- **Paper trade FIRST** -- Run in paper trading mode for 2+ weeks minimum before considering live trading
- **Start with minimal capital** -- If you choose to trade live, start with the smallest possible amounts ($100-500 max)
- **You assume ALL risk** -- The authors accept NO liability for any financial losses

**By using this software, you acknowledge these risks and take full responsibility for your trading decisions.**

---

## Features

**Core Trading**
- Real-time multi-exchange arbitrage detection (<50ms latency via WebSocket)
- 6-factor ML opportunity scoring with Almgren-Chriss slippage estimation
- Triangle arbitrage detection across trading pairs
- Circuit breaker pattern for fault tolerance
- Order book depth validation before execution

**Risk Management**
- Kelly Criterion position sizing (capped at 10-25%)
- VaR (95%) and Sharpe/Sortino ratio tracking
- Automatic position rebalancing on partial fills
- Graceful shutdown with position closing

**Security**
- Fernet-encrypted API credentials in memory
- Rate limiting with LRU eviction
- SSL verification on all connections

**Operations**
- Kubernetes-ready health probes (liveness/readiness)
- Prometheus metrics and Grafana dashboards
- Alertmanager integration with PagerDuty/Slack routing

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 14+ with TimescaleDB
- Redis 6+
- 4GB RAM minimum

### Setup

```bash
# Clone and configure
git clone https://github.com/yourusername/carbs.git
cd carbs/crypto-arbitrage-system

# Create venv and install
make setup
# Or manually:
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env   # Add API keys (leave empty for paper trading)

# Start infrastructure
make start             # docker compose up -d (postgres, redis, prometheus)
make db-init           # Initialize database

# Run (paper trading by default)
python src/advanced_main.py
```

### Verify Installation

```
2025-10-27 15:30:00 - INFO - Initializing Arbitrage Engine...
2025-10-27 15:30:01 - INFO - Initialized 3 exchanges
2025-10-27 15:30:01 - INFO - Monitoring: BTC/USDT, ETH/USDT
2025-10-27 15:30:01 - INFO - PAPER TRADING MODE
```

### Accessing Services

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3000 | admin/admin |
| Prometheus | http://localhost:9090 | -- |
| Metrics | http://localhost:8000/metrics | -- |
| PostgreSQL | localhost:5432 | see .env |
| Redis | localhost:6379 | see .env |

---

## Configuration

### config/config.yaml

```yaml
trading:
  mode: paper              # paper | live
  min_spread_percent: 0.3  # Minimum spread to consider
  max_spread_percent: 5.0  # Maximum spread (sanity check)
  max_position_usd: 500    # Maximum position size

exchanges:
  binance:
    enabled: true
    taker_fee: 0.001       # 0.1%
  coinbase:
    enabled: true
    taker_fee: 0.006       # 0.6%

symbols:
  - BTC/USDT
  - ETH/USDT

risk:
  max_daily_loss_usd: 100
  max_drawdown_percent: 10
  kelly_fraction: 0.25
```

### Environment Variables (.env)

```bash
# Required
POSTGRES_DB=arbitrage
POSTGRES_USER=arbitrage_user
POSTGRES_PASSWORD=<your-password>
REDIS_HOST=localhost
CARBS_MASTER_KEY=<generated-key>  # python -c "import secrets; print(secrets.token_urlsafe(32))"

# Exchange API Keys (leave empty for paper trading)
BINANCE_API_KEY=
BINANCE_API_SECRET=

# Optional
USER_JURISDICTION=US    # Enforces KuCoin block for US persons
LOG_LEVEL=INFO
```

Configuration precedence (highest to lowest): Environment variables > `.env` file > `config/config.yaml` > Code defaults.

---

## Architecture

```
+-------------------------------------------------+
|  Advanced Arbitrage Engine                       |
|  +- ML Scoring (6-factor composite)             |
|  +- Execution Engine (circuit breakers)          |
|  +- Risk Manager (Kelly, VaR, Sharpe)            |
+-------------------------------------------------+
|  Infrastructure                                  |
|  +- PostgreSQL + TimescaleDB (time-series)       |
|  +- Redis (orderbook cache, 1s TTL)              |
|  +- Prometheus + Grafana (monitoring)            |
+-------------------------------------------------+
|  Exchange Layer (CCXT Pro WebSocket)             |
|  +- Binance, Coinbase, Kraken, OKX, Bybit       |
+-------------------------------------------------+
```

### Data Flow

```
Exchange APIs -> CCXT Pro (WS) -> Engine -> Redis Cache
                                       |
                                Opportunity Detection
                                       |
                                PostgreSQL/TimescaleDB
                                       |
                                Grafana Analytics
```

### Performance

| Metric | Target | Status |
|--------|--------|--------|
| End-to-end latency | <100ms | Async optimization |
| Throughput | 1000+/sec | Concurrent processing |
| Execution accuracy | >95% | Circuit breakers + retry |
| Storage efficiency | 90% reduction | TimescaleDB compression |

---

## Project Structure

```
crypto-arbitrage-system/
+-- src/
|   +-- core/           # Arbitrage engine, execution, risk management
|   +-- exchanges/      # CCXT Pro exchange adapters
|   +-- api/            # FastAPI health/metrics endpoints
|   +-- database/       # TimescaleDB models via asyncpg
|   +-- utils/          # Credentials, cache, metrics
|   +-- compliance/     # Tax, regulatory, Form 1099-DA
+-- config/             # YAML configs, Prometheus alerts
+-- tests/              # pytest test suite
+-- docker/             # Docker configurations
+-- scripts/            # Utility and analysis scripts
+-- docs/               # Additional documentation
```

---

## Key Commands

```bash
make setup          # Create venv + install dependencies
make start          # docker compose up -d
make stop           # Stop Docker containers
make db-init        # Initialize database
make run            # Run the bot
make test           # pytest tests/ -v --cov=src
make lint           # flake8 + mypy
make format         # black + isort
make logs           # View Docker logs
make clean          # Clean everything
```

---

## Exchange Support (US Persons)

| Exchange | Status | Notes |
|----------|--------|-------|
| Binance.US | Supported | Recommended for US |
| Kraken | Supported | Good alternative |
| Coinbase Pro | Supported | Higher fees |
| MEXC | Restricted | Geographic restrictions |
| KuCoin | **PROHIBITED** | CFTC/FinCEN enforcement -- blocked when `USER_JURISDICTION=US` |

---

## Safety: Before Live Trading

**Paper trading is the default mode.** Before going live:

1. Run paper trading for 2+ weeks (4 weeks recommended)
2. Verify profitability after all costs (fees + slippage > 0.2%)
3. Complete the go-live checklist in [DEPLOYMENT.md](DEPLOYMENT.md)
4. Start with minimal capital ($100-500)
5. Monitor via Grafana dashboards

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete production deployment procedures.

---

## Legal Obligations

As a personal trader, you are responsible for:

- **KYC**: Complete identity verification on all exchanges
- **2FA**: Enable two-factor authentication (mandatory)
- **Taxes**: Report all profits (IRS Form 8949, Schedule D)
- **Records**: Keep trade records for 7 years
- **Exchange ToS**: Accept Terms of Service on each exchange

CARBS generates tax exports (Form 8949, Missouri MO-A worksheets, 1099-DA reconciliation). See [COMPLIANCE.md](COMPLIANCE.md) for details.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Containers won't start | `docker compose down -v && docker compose up -d` |
| Database connection issues | Wait 30 seconds after starting containers |
| No opportunities found | Normal -- arbitrage is rare. Let run 24+ hours |
| Import errors | `source venv/bin/activate && pip install -r requirements.txt` |
| Redis connection refused | `docker compose restart redis` |

---

## Documentation

| Document | Purpose |
|----------|---------|
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development guide, code standards, architecture |
| [SECURITY.md](SECURITY.md) | Security policy, API key management |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production deployment, go-live checklist, runbook |
| [COMPLIANCE.md](COMPLIANCE.md) | Tax, regulatory, exchange ToS compliance |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

---

## License

MIT License - see [LICENSE](LICENSE)

---

*Educational purposes only. Cryptocurrency trading carries significant risk of loss. This software is provided "as is" without warranty. Use at your own risk.*
