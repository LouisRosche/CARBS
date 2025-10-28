# Quick Start Guide

## Prerequisites

- Ubuntu 24.04 or macOS
- Docker & Docker Compose
- Python 3.11+
- Git

## 5-Minute Setup

```bash
# 1. Clone repository
git clone https://github.com/yourusername/crypto-arbitrage-system.git
cd crypto-arbitrage-system

# 2. Setup environment
make setup

# 3. Edit configuration
nano .env
# Set your credentials (leave API keys empty for paper trading)

# 4. Start infrastructure
make start

# Wait 30 seconds for containers to start

# 5. Initialize database
make db-init

# 6. Run the bot!
make run
```

## What You Should See

```
2025-10-27 15:30:00 - INFO - 🚀 Initializing Arbitrage Engine...
2025-10-27 15:30:01 - INFO - ✅ Initialized 3 exchanges
2025-10-27 15:30:01 - INFO - 📊 Monitoring: BTC/USDT, ETH/USDT
2025-10-27 15:30:01 - INFO - 📝 PAPER TRADING MODE
2025-10-27 15:30:03 - INFO - ✨ BTC/USDT: 0.45% | Buy binance @ $67543.21 | Sell kraken @ $67847.89 | Profit: $22.50
```

## Next Steps

1. **Let it run for 24 hours** to collect data
2. **Check Grafana**: http://localhost:3000 (admin/admin)
3. **View opportunities**:
   ```bash
   make logs
   ```
4. **Analyze results**:
   ```bash
   python scripts/analyze.py
   ```

## Common Issues

### Docker containers won't start
```bash
docker compose down -v
docker compose up -d
```

### Database connection error
```bash
# Wait for PostgreSQL to fully start (30 seconds)
docker compose logs postgres
```

### No opportunities found
- Normal! Profitable opportunities are rare
- Let run for 24+ hours
- Check exchange connectivity: `docker compose logs`
