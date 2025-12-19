# CARBS - Crypto Arbitrage Bot System

Production-ready cryptocurrency arbitrage detection and execution platform.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Production Ready](https://img.shields.io/badge/Production-Ready%20(95%25)-green.svg)](PRODUCTION_READINESS_REPORT.md)
[![codecov](https://codecov.io/gh/LouisRosche/CARBS/branch/main/graph/badge.svg)](https://codecov.io/gh/LouisRosche/CARBS)

---

## 🚀 Quick Navigation

**New to CARBS?** Choose your starting point:

| Your Goal | Start Here | Time |
|-----------|------------|------|
| **First time here?** | 📍 **[START_HERE.md](START_HERE.md)** | 5 min |
| **Ready to deploy?** | 📊 [PRODUCTION_READINESS_REPORT.md](PRODUCTION_READINESS_REPORT.md) | 20 min |
| **Looking for specific docs?** | 📚 [DOCUMENTATION_HUB.md](DOCUMENTATION_HUB.md) | 10 min |
| **Want to contribute?** | 💻 [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) | 1-2 hrs |

**Current Status:** ✅ Production Ready - Grade A (95%)

---

## ⚠️ **CRITICAL: RISK DISCLAIMER**

**🚨 CRYPTOCURRENCY TRADING CARRIES SIGNIFICANT FINANCIAL RISK 🚨**

- **This software is for EDUCATIONAL and RESEARCH purposes**
- **NOT financial advice** — Consult qualified professionals before trading
- **You can LOSE ALL your capital** — Never invest more than you can afford to lose
- **No profitability guarantees** — Past performance does not indicate future results
- **Paper trade FIRST** — Run in paper trading mode for 2+ weeks minimum before considering live trading
- **Start with minimal capital** — If you choose to trade live, start with the smallest possible amounts ($100-500 max)
- **You assume ALL risk** — The authors accept NO liability for any financial losses

**By using this software, you acknowledge these risks and take full responsibility for your trading decisions.**

📋 See [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) for detailed safety checklist before live trading.

---

## Features

**Core Trading**
- Real-time multi-exchange arbitrage detection (<50ms latency via WebSocket)
- 6-factor ML opportunity scoring with Almgren-Chriss slippage estimation
- Triangle arbitrage detection across trading pairs
- Circuit breaker pattern for fault tolerance
- Order book depth validation before execution

**Risk Management**
- Kelly Criterion position sizing
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

## Quick Start

```bash
# Clone and configure
git clone https://github.com/yourusername/carbs.git
cd carbs/crypto-arbitrage-system
cp .env.example .env  # Add API keys

# Start infrastructure
docker compose up -d

# Run (paper trading by default)
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python src/advanced_main.py
```

## Configuration

```yaml
# config/config.yaml
trading:
  mode: paper  # paper | live
  min_spread_percent: 0.3
  max_position_usd: 500

exchanges:
  binance: { enabled: true, taker_fee: 0.001 }
  coinbase: { enabled: true, taker_fee: 0.006 }

symbols: [BTC/USDT, ETH/USDT]
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Advanced Arbitrage Engine                       │
│  ├─ ML Scoring (6-factor composite)             │
│  ├─ Execution Engine (circuit breakers)         │
│  └─ Risk Manager (Kelly, VaR, Sharpe)           │
├─────────────────────────────────────────────────┤
│  Infrastructure                                  │
│  ├─ PostgreSQL + TimescaleDB (time-series)      │
│  ├─ Redis (orderbook cache, 1s TTL)             │
│  └─ Prometheus + Grafana (monitoring)           │
├─────────────────────────────────────────────────┤
│  Exchange Layer (CCXT Pro WebSocket)            │
│  └─ Binance, Coinbase, Kraken, OKX, Bybit       │
└─────────────────────────────────────────────────┘
```

## Project Structure

```
crypto-arbitrage-system/
├── src/
│   ├── core/           # Arbitrage, execution, risk management
│   ├── exchanges/      # Exchange adapters with secure credentials
│   ├── api/            # Health checks, middleware
│   ├── database/       # TimescaleDB models
│   └── utils/          # Secure credentials, cache, metrics
├── config/             # YAML configs, Prometheus alerts
├── tests/              # Unit and integration tests
└── docker/             # Docker configurations
```

## Safety

**Paper trading is the default mode.** Before live trading:

1. Run paper trading for 2+ weeks
2. Verify profitability after all costs
3. Start with minimal capital
4. Monitor via Grafana dashboards

## License

MIT License - see [LICENSE](LICENSE)

---

*Educational purposes only. Cryptocurrency trading carries significant risk.*
