# Deployment Guide

**DO NOT skip any section before live trading with real capital.**

---

## Table of Contents

1. [Risk Acknowledgment](#risk-acknowledgment)
2. [Deployment Options](#deployment-options)
3. [Infrastructure Setup](#infrastructure-setup)
4. [Configuration](#configuration)
5. [Paper Trading (Mandatory)](#paper-trading-mandatory)
6. [Production Readiness Checklist](#production-readiness-checklist)
7. [Go-Live Procedure](#go-live-procedure)
8. [Operations Runbook](#operations-runbook)
9. [Scaling and Maintenance](#scaling-and-maintenance)

---

## Risk Acknowledgment

**Cryptocurrency trading can result in total loss of capital. Only proceed if:**

- You fully understand arbitrage trading mechanics
- You can afford to lose 100% of your trading capital
- You accept FULL responsibility for all trading outcomes
- You will paper trade first for 2+ weeks minimum
- You will start with minimal capital ($100-500)

---

## Deployment Options

| Option | Cost | Best For | Uptime |
|--------|------|----------|--------|
| Pure Local | $5-10/mo (power) | Paper trading, learning | When machine is on |
| Local + VPS Fallback | $10-20/mo | Live trading with reliability | ~99.9% |
| Dedicated Mini Server | $2-3/mo (power) | Serious local-first operation | ~99% |
| Cloud VPS Only | $12-50/mo | Always-on production | ~99.9% |

### Docker Compose (Recommended)

```bash
# Clone and configure
git clone https://github.com/yourusername/carbs.git
cd carbs/crypto-arbitrage-system

make setup          # Create venv + install dependencies
cp .env.example .env
# Edit .env with your credentials

make start          # docker compose up -d (postgres, redis, prometheus)
make db-init        # Initialize database
make run            # Start the bot (paper mode by default)
```

### VPS Deployment (DigitalOcean/Linode)

```bash
# On VPS: Ubuntu 24.04 LTS, 2GB RAM, 2 vCPUs (~$12/month)
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
apt install python3.11 python3.11-venv docker-compose-plugin -y

git clone https://github.com/yourusername/carbs.git
cd carbs/crypto-arbitrage-system
make setup && make start && make db-init
```

#### systemd Service (for always-on operation)

```bash
cat > /etc/systemd/system/arbitrage.service << 'EOF'
[Unit]
Description=Crypto Arbitrage System
After=docker.service

[Service]
Type=simple
WorkingDirectory=/root/crypto-arbitrage-system
ExecStart=/root/crypto-arbitrage-system/venv/bin/python src/advanced_main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl enable arbitrage && systemctl start arbitrage
```

---

## Infrastructure Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 14+ with TimescaleDB
- Redis 6+
- 4GB RAM minimum (8GB recommended)

### Verify Services

```bash
# PostgreSQL
docker compose exec postgres pg_isready

# Redis
docker compose exec redis redis-cli ping  # Should return PONG

# Application health
curl http://localhost:8000/health
```

### Security Hardening

```bash
# Firewall (Ubuntu)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw enable

# Protect .env
chmod 600 .env

# Generate master key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Configuration

### Exchange Account Setup

**For US residents:** Use Binance.US + Kraken or Coinbase (MEXC and KuCoin are prohibited).

For each exchange:
1. Create account and complete KYC
2. Enable 2FA (authenticator app, not SMS)
3. Create API key with **trading only** permissions -- **disable withdrawals**
4. Enable IP whitelisting
5. Accept Terms of Service
6. Copy API key and secret to `.env`

### Environment File (.env)

```bash
# Required
POSTGRES_DB=arbitrage
POSTGRES_USER=arbitrage_user
POSTGRES_PASSWORD=<your-password>
REDIS_HOST=localhost
CARBS_MASTER_KEY=<generated-key>

# Exchange API Keys (leave empty for paper trading)
BINANCE_API_KEY=
BINANCE_API_SECRET=

# Jurisdiction (blocks prohibited exchanges)
USER_JURISDICTION=US

# Trading
TRADING_MODE=paper    # Start with paper!
LOG_LEVEL=INFO
```

### Config File (config/config.yaml)

```yaml
trading:
  mode: paper              # paper | live
  min_spread_percent: 0.3
  max_spread_percent: 5.0
  max_position_usd: 500
  max_daily_loss_usd: 100

exchanges:
  binance:
    enabled: true
    taker_fee: 0.001
  kraken:
    enabled: true
    taker_fee: 0.0026
  kucoin:
    enabled: false         # MUST stay false for US persons

symbols:
  - BTC/USDT
  - ETH/USDT

risk:
  max_drawdown_percent: 10
  kelly_fraction: 0.25
```

---

## Paper Trading (Mandatory)

**Duration: Minimum 2 weeks, recommended 4 weeks.**

### Start Paper Trading

```bash
# Confirm mode is paper in config.yaml
make run
# Verify "PAPER TRADING MODE" appears in logs
```

### Week 1-2: System Stability

- [ ] System runs continuously without crashes
- [ ] No critical errors in logs (check `data/logs/` daily)
- [ ] Opportunities detected regularly
- [ ] All exchanges connect successfully
- [ ] Database persists data correctly
- [ ] Redis cache functions properly

### Week 3-4: Profitability Analysis

Track these metrics:

| Metric | Your Value | Target |
|--------|------------|--------|
| Average spread after fees + slippage | _____% | > 0.2% |
| Opportunities per day | _____ | > 10 |
| False positive rate | _____% | < 50% |
| System uptime | _____% | > 99% |
| Estimated monthly ROI | _____% | > 5% |

### Decision Points

| Result | Action |
|--------|--------|
| All green (targets met) | Proceed to go-live |
| Any yellow (marginal) | Extend paper trading, optimize |
| Any red (below targets) | Do NOT go live |

**If average spread after fees + slippage < 0.2%, STOP -- not profitable.**

---

## Production Readiness Checklist

### Technical Validation

- [ ] All tests pass: `make test`
- [ ] Latency benchmarks pass: `pytest tests/test_performance.py`
  - End-to-end: <100ms
  - Orderbook processing: <10ms
  - Spread calculation: <1ms
- [ ] Database backups automated (daily minimum)
- [ ] Monitoring stack operational (Prometheus + Grafana)
- [ ] Alert channels configured and tested

### Security Audit

- [ ] API keys: trading only, NO withdrawal permissions
- [ ] IP whitelisting enabled on all exchanges
- [ ] Master encryption key set (`CARBS_MASTER_KEY`)
- [ ] `.env` permissions: `chmod 600`
- [ ] No secrets in git: `git log --all --full-history --source -- .env`
- [ ] Security scan: `bandit -r src/`
- [ ] Audit logging enabled and verified

### Risk Management

- [ ] `max_position_usd`: $100-500 for first month
- [ ] `min_spread_percent`: 0.5-1.0% (must cover fees + slippage + margin)
- [ ] Daily loss limit configured
- [ ] Circuit breaker tested
- [ ] Emergency stop tested (Ctrl+C or `docker compose down`)
- [ ] Graceful shutdown closes positions

### Financial Setup

- [ ] Exchange accounts funded with minimal capital ($500-2000 total)
- [ ] Balance distributed across exchanges (roughly equal per exchange)
- [ ] Tax record-keeping configured (compliance module)

---

## Go-Live Procedure

### Pre-Launch (Day 0)

```bash
# Final verification
make test
grep "mode:" config/config.yaml  # Should be: mode: paper (still)

# Backup
docker compose exec postgres pg_dump -U arbitrage arbitrage > backup_$(date +%Y%m%d).sql

# Switch to live
# Edit config/config.yaml: mode: live
# Set conservative limits:
#   max_position_usd: 100
#   max_daily_trades: 5
#   max_daily_loss_usd: 20
```

### Launch

```bash
make start       # Ensure infrastructure running
make run         # Start with live mode

# Verify "LIVE TRADING MODE" in logs
# Keep logs tailing: make logs
# Open Grafana dashboard
```

### First Hour (Monitor Constantly)

- [ ] Exchange connections successful
- [ ] Orderbook data streaming
- [ ] Watch for first opportunity detection
- [ ] Verify first trade executes correctly (check exchange UI)
- [ ] Monitor for any errors

### First Week (Monitor Closely)

Daily checks (3x/day -- morning, midday, evening):
- [ ] System running, no errors
- [ ] Balances correct on exchanges
- [ ] Review trades executed
- [ ] Calculate actual vs. expected profits

**STOP if:** Net loss > $50, more than 2 failed trades, any unexplained errors, results much worse than paper trading.

### First Month

- [ ] Weekly performance reviews
- [ ] Compare actual vs. paper trading results
- [ ] Gradual limit increases if profitable:
  - Week 2: `max_position_usd: 200`
  - Week 3: `max_position_usd: 300`
  - Month 2+: `max_position_usd: 500`

---

## Operations Runbook

### Emergency: Stop Trading Immediately

**When:** Unexpected losses, erratic behavior, security breach suspected.

```bash
docker compose down
# OR: pkill -f "python.*main.py"

# Check for open positions on exchange web UIs
# Manually close any open positions if necessary
# Check logs:
tail -100 data/logs/app.log

# DO NOT restart until issue identified and resolved
```

### Daily Health Check (5 minutes)

```bash
# Application running?
ps aux | grep "python.*main.py" | grep -v grep

# Infrastructure status
docker compose ps

# Recent errors
grep -i "error\|critical" data/logs/app.log | tail -10

# Exchange connectivity
curl -s https://api.binance.com/api/v3/ping && echo "Binance OK"
```

### Common Issues

| Problem | Diagnosis | Resolution |
|---------|-----------|------------|
| App won't start | `docker compose ps`, check `.env` | `docker compose down -v && docker compose up -d && make db-init` |
| No opportunities | Normal -- arbitrage is rare | Let run 24+ hours; check exchange connectivity |
| Database connection | `docker compose exec postgres pg_isready` | `docker compose restart postgres`, wait 10s |
| Redis connection | `docker compose exec redis redis-cli ping` | `docker compose restart redis` |
| High memory | `docker stats --no-stream` | Set Redis maxmemory: `CONFIG SET maxmemory 256mb` |
| Trades not executing | Check `mode:` in config.yaml, check API keys | Verify balance, API permissions, paper vs. live mode |
| High latency (>100ms) | `pytest tests/test_performance.py` | Check network: `ping api.binance.com`; check DB queries |

### Database Operations

```bash
# Backup
docker compose exec postgres pg_dump -U arbitrage arbitrage > backup_$(date +%Y%m%d).sql

# Restore
cat backup.sql | docker compose exec -T postgres psql -U arbitrage arbitrage

# Maintenance
docker compose exec postgres psql -U arbitrage -c "VACUUM FULL;"
docker compose exec postgres psql -U arbitrage -c "ANALYZE;"

# Check size
docker compose exec postgres psql -U arbitrage -c \
  "SELECT pg_size_pretty(pg_database_size('arbitrage'));"

# Recent opportunities
docker compose exec postgres psql -U arbitrage -c \
  "SELECT symbol, buy_exchange, sell_exchange, spread_percent, detected_at
   FROM opportunities ORDER BY detected_at DESC LIMIT 10;"
```

### Log Analysis

```bash
# Errors in last hour
grep -E "ERROR|CRITICAL" data/logs/app.log | tail -20

# Top error messages
grep "ERROR" data/logs/app.log | cut -d'-' -f4- | sort | uniq -c | sort -rn | head -10

# Audit trail
grep '"category": "trading"' data/audit/audit.log | tail -10
```

### Exchange API Issues

| Exchange | Status Page | Test Command |
|----------|------------|--------------|
| Binance | binance.com/en/support/announcement | `curl https://api.binance.com/api/v3/ping` |
| Coinbase | status.coinbase.com | `curl https://api.coinbase.com/v2/time` |
| Kraken | status.kraken.com | `curl https://api.kraken.com/0/public/Time` |

Common errors: `429` = rate limited (wait 60s), `418` = IP banned (contact support), `1002` = invalid API key.

---

## Scaling and Maintenance

### Ongoing Schedule

| Frequency | Task | Time |
|-----------|------|------|
| Daily | Check logs, verify system running, check balances | 5 min |
| Weekly | Review performance, verify backups, check for updates | 30 min |
| Monthly | Security audit, rotate API keys, review risk parameters, tax reconciliation | 1 hour |
| Quarterly | Full compliance review, estimated tax calculation, review regulatory changes | 2 hours |
| Annually | File taxes (Form 8949, Schedule D), archive audit logs (7-year retention) | 4 hours |

### Scaling Guidelines

**Only increase capital after:**
- 3+ months of profitable operation
- Consistent Sharpe ratio > 1.5
- Win rate > 70%
- No critical incidents in last 30 days

**Rules:**
- Increase capital by MAX 50% per month
- Never deploy more than you can afford to lose
- Monitor for diminishing returns (market impact)

### Backup Strategy

```bash
# Automated daily backup (add to crontab)
0 2 * * * docker compose exec -T postgres pg_dump -U arbitrage arbitrage | gzip > /backups/carbs_$(date +\%Y\%m\%d).sql.gz

# Full system backup
tar -czvf carbs_backup_$(date +%Y%m%d).tar.gz .env data/ config/
gpg -c carbs_backup_$(date +%Y%m%d).tar.gz
```

---

*This guide is for reference only. Completing these steps does not guarantee profitability. Trading cryptocurrency carries significant risk of loss.*
