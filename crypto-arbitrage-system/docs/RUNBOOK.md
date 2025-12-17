# CARBS Operations Runbook

**Purpose:** Quick reference for troubleshooting and resolving common operational issues.

**Audience:** System operators, on-call engineers, DevOps teams

**Last Updated:** 2025-12-17

---

## Table of Contents

1. [Emergency Procedures](#emergency-procedures)
2. [Common Issues](#common-issues)
3. [System Health Checks](#system-health-checks)
4. [Log Analysis](#log-analysis)
5. [Database Operations](#database-operations)
6. [Exchange API Issues](#exchange-api-issues)
7. [Performance Troubleshooting](#performance-troubleshooting)
8. [Security Incidents](#security-incidents)

---

## Emergency Procedures

### 🔴 STOP TRADING IMMEDIATELY

**When:** Unexpected losses, system behaving erratically, security breach suspected

**Steps:**
```bash
# 1. Stop the application
docker compose down

# OR if running directly:
pkill -f "python.*main.py"

# 2. Check for open positions on exchanges (via web UI)
# 3. Manually close any open positions if necessary
# 4. Check logs for cause
tail -100 data/logs/app.log
tail -100 data/audit/audit.log

# 5. DO NOT restart until issue identified and resolved
```

**Escalation:** Contact primary maintainer immediately if unable to resolve.

---

## Common Issues

### Issue: Application Won't Start

**Symptoms:** Error on startup, immediate crash

**Diagnosis:**
```bash
# Check if infrastructure is running
docker compose ps

# Check logs
docker compose logs postgres
docker compose logs redis

# Verify environment variables
cat .env | grep -v "^#" | grep -v "^$"
```

**Common Causes:**

1. **Database not ready**
   ```bash
   # Wait 30 seconds after docker compose up
   sleep 30
   # Or check manually
   docker compose exec postgres pg_isready
   ```

2. **Missing .env file**
   ```bash
   cp .env.example .env
   # Edit .env with actual values
   ```

3. **Invalid API keys**
   ```bash
   # Verify keys in exchange web UI
   # Check key permissions (should allow trading, not withdrawals)
   ```

4. **Port conflicts**
   ```bash
   # Check if ports are in use
   lsof -i :5432  # PostgreSQL
   lsof -i :6379  # Redis
   lsof -i :3000  # Grafana
   ```

**Resolution:**
```bash
# Clean restart
docker compose down -v
docker compose up -d
sleep 30
make db-init
python src/main.py
```

---

### Issue: No Opportunities Detected

**Symptoms:** System running but no arbitrage opportunities found

**Diagnosis:**
```bash
# Check exchange connections
grep "exchange.*connected\|exchange.*failed" data/logs/app.log

# Check orderbook updates
grep "orderbook" data/logs/app.log | tail -20

# Query database for recent data
docker compose exec postgres psql -U arbitrage -c \
  "SELECT exchange, symbol, COUNT(*) FROM orderbooks
   WHERE timestamp > NOW() - INTERVAL '5 minutes'
   GROUP BY exchange, symbol;"
```

**Common Causes:**

1. **Markets are efficient** (this is normal!)
   - Arbitrage opportunities are rare
   - May go hours without profitable spreads
   - **Action:** None, this is expected

2. **Exchange API failures**
   ```bash
   # Check exchange status pages
   curl -s https://api.binance.com/api/v3/ping
   ```

3. **Minimum spread too high**
   - Check `config/config.yaml`
   - `min_spread_percent: 0.3` means 0.3% minimum
   - Lower if needed, but balance against fees

4. **Stale orderbook data**
   - Check timestamps in logs
   - If >5 seconds old, WebSocket may have disconnected

**Resolution:**
```bash
# Restart to re-establish WebSocket connections
docker compose restart
```

---

### Issue: Database Connection Errors

**Symptoms:** `ConnectionError: could not connect to database`

**Diagnosis:**
```bash
# Check if PostgreSQL is running
docker compose ps postgres

# Check database logs
docker compose logs postgres | tail -50

# Test connection
docker compose exec postgres psql -U arbitrage -c "SELECT 1;"
```

**Common Causes:**

1. **PostgreSQL not started**
   ```bash
   docker compose up -d postgres
   sleep 10
   ```

2. **Wrong credentials**
   ```bash
   # Verify .env matches docker-compose.yml
   grep POSTGRES .env
   ```

3. **Connection pool exhausted**
   ```bash
   # Check for idle connections
   docker compose exec postgres psql -U arbitrage -c \
     "SELECT count(*) FROM pg_stat_activity;"

   # If >100, may need to restart
   docker compose restart
   ```

4. **Disk full**
   ```bash
   df -h
   # If >90% full, clean up old logs/data
   ```

**Resolution:**
```bash
# Restart database
docker compose restart postgres
sleep 10

# If still failing, recreate
docker compose down
docker volume rm crypto-arbitrage-system_postgres_data
docker compose up -d
make db-init
```

---

### Issue: Redis Connection Errors

**Symptoms:** `ConnectionError: could not connect to Redis`

**Diagnosis:**
```bash
# Check if Redis is running
docker compose ps redis

# Test connection
docker compose exec redis redis-cli ping
# Should return: PONG
```

**Resolution:**
```bash
# Restart Redis
docker compose restart redis

# If data corruption suspected
docker compose stop redis
docker volume rm crypto-arbitrage-system_redis_data
docker compose up -d redis
```

---

### Issue: High Memory Usage

**Symptoms:** System slow, OOM errors, crashed

**Diagnosis:**
```bash
# Check memory usage
docker stats --no-stream

# Check for memory leaks in app
ps aux | grep python

# Check database cache size
docker compose exec postgres psql -U arbitrage -c \
  "SHOW shared_buffers;"
```

**Common Causes:**

1. **Large orderbook accumulation**
   - Check if orderbooks being cached indefinitely
   - Should be cleared after use

2. **Database connection leak**
   - Check for unclosed connections
   - Use connection pooling

3. **Redis memory not limited**
   ```bash
   # Check Redis memory usage
   docker compose exec redis redis-cli INFO memory
   ```

**Resolution:**
```bash
# Set Redis max memory
docker compose exec redis redis-cli CONFIG SET maxmemory 256mb
docker compose exec redis redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Restart application to clear memory
docker compose restart
```

---

### Issue: Trades Not Executing

**Symptoms:** Opportunities detected but orders not placed

**Diagnosis:**
```bash
# Check if in paper trading mode
grep "mode:" config/config.yaml
# Should be: mode: live (for live trading)

# Check exchange API keys
grep "API_KEY" .env | wc -l
# Should have keys for each enabled exchange

# Check audit logs for execution attempts
grep "execute\|trade" data/audit/audit.log | tail -20

# Check for insufficient balance
docker compose exec postgres psql -U arbitrage -c \
  "SELECT * FROM balances ORDER BY updated_at DESC LIMIT 10;"
```

**Common Causes:**

1. **Paper trading mode enabled**
   - Change `mode: paper` to `mode: live` in config.yaml
   - **WARNING:** Only do this after thorough testing!

2. **Insufficient balance**
   - Check exchange balances via web UI
   - Ensure funds on both buy and sell exchanges

3. **Order size too small**
   - Exchanges have minimum order sizes
   - Check exchange documentation

4. **API permissions insufficient**
   - Keys need trading permission
   - Verify in exchange web UI

**Resolution:**
```bash
# If in paper mode and ready for live (BE CAREFUL!)
sed -i 's/mode: paper/mode: live/' config/config.yaml

# Restart to pick up config changes
docker compose restart
```

---

## System Health Checks

### Daily Health Check (5 minutes)

```bash
#!/bin/bash
# save as: scripts/health_check.sh

echo "=== CARBS Health Check ==="
echo "Date: $(date)"
echo ""

# 1. System uptime
echo "1. Application Status:"
ps aux | grep "python.*main.py" | grep -v grep && echo "✅ Running" || echo "❌ NOT RUNNING"
echo ""

# 2. Infrastructure
echo "2. Infrastructure:"
docker compose ps
echo ""

# 3. Recent opportunities
echo "3. Opportunities (last hour):"
docker compose exec -T postgres psql -U arbitrage -c \
  "SELECT COUNT(*) as opportunities
   FROM opportunities
   WHERE detected_at > NOW() - INTERVAL '1 hour';" 2>/dev/null || echo "❌ Database unavailable"
echo ""

# 4. Disk space
echo "4. Disk Space:"
df -h | grep -E "Filesystem|/$"
echo ""

# 5. Recent errors
echo "5. Recent Errors (last 24h):"
grep -i "error\|critical" data/logs/app.log 2>/dev/null | grep "$(date +%Y-%m-%d)" | wc -l
echo ""

# 6. Exchange connectivity
echo "6. Exchange Connectivity:"
curl -s -m 5 https://api.binance.com/api/v3/ping && echo "✅ Binance" || echo "❌ Binance"
curl -s -m 5 https://api.coinbase.com/v2/time && echo "✅ Coinbase" || echo "❌ Coinbase"
echo ""

echo "=== End Health Check ==="
```

**Run:**
```bash
chmod +x scripts/health_check.sh
./scripts/health_check.sh
```

---

## Log Analysis

### Find Errors in Last Hour

```bash
grep -E "ERROR|CRITICAL" data/logs/app.log | \
  awk -v d="$(date -d '1 hour ago' '+%Y-%m-%d %H:%M')" '$0 > d'
```

### Top Error Messages

```bash
grep "ERROR" data/logs/app.log | \
  cut -d'-' -f4- | sort | uniq -c | sort -rn | head -10
```

### Audit Log Verification

```bash
# Verify audit log integrity
python -c "
from security.audit import AuditLogger
logger = AuditLogger()
is_valid, broken = logger.verify_integrity()
if is_valid:
    print('✅ Audit log integrity: OK')
else:
    print(f'❌ Audit log integrity: BROKEN')
    print(f'Broken events: {broken}')
"
```

### Query Audit Logs

```bash
# Failed login attempts
grep '"action": "login"' data/audit/audit.log | grep '"success": false'

# All trades in last 24h
grep '"category": "trading"' data/audit/audit.log | \
  grep "$(date +%Y-%m-%d)"

# Configuration changes
grep '"category": "configuration"' data/audit/audit.log
```

---

## Database Operations

### Manual Queries

```bash
# Connect to database
docker compose exec postgres psql -U arbitrage

# Common queries:

-- Recent opportunities
SELECT symbol, buy_exchange, sell_exchange, spread_percent, detected_at
FROM opportunities
ORDER BY detected_at DESC
LIMIT 10;

-- Trade history
SELECT * FROM trades
WHERE executed_at > NOW() - INTERVAL '24 hours'
ORDER BY executed_at DESC;

-- Current balances
SELECT * FROM balances
ORDER BY updated_at DESC;

-- Performance metrics
SELECT
  DATE(detected_at) as date,
  COUNT(*) as opportunities,
  AVG(spread_percent) as avg_spread,
  MAX(spread_percent) as max_spread
FROM opportunities
WHERE detected_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(detected_at)
ORDER BY date DESC;
```

### Database Backup

```bash
# Backup database
docker compose exec postgres pg_dump -U arbitrage arbitrage > backup_$(date +%Y%m%d).sql

# Restore database
cat backup_20251217.sql | docker compose exec -T postgres psql -U arbitrage arbitrage
```

### Database Maintenance

```bash
# Vacuum database (reclaim space)
docker compose exec postgres psql -U arbitrage -c "VACUUM FULL;"

# Analyze tables (update statistics)
docker compose exec postgres psql -U arbitrage -c "ANALYZE;"

# Check database size
docker compose exec postgres psql -U arbitrage -c \
  "SELECT pg_size_pretty(pg_database_size('arbitrage'));"
```

---

## Exchange API Issues

### Binance

**Status:** https://www.binance.com/en/support/announcement

**Test Connection:**
```bash
curl https://api.binance.com/api/v3/ping
```

**Common Errors:**
- `429 Too Many Requests`: Rate limited. Wait 60 seconds.
- `418 IP Banned`: IP banned. Contact Binance support.
- `1002 Unauthorized`: Invalid API key or signature.

### Coinbase

**Status:** https://status.coinbase.com/

**Test Connection:**
```bash
curl https://api.coinbase.com/v2/time
```

### Kraken

**Status:** https://status.kraken.com/

**Test Connection:**
```bash
curl https://api.kraken.com/0/public/Time
```

---

## Performance Troubleshooting

### Latency Too High

**Check latency:**
```bash
# Run performance benchmarks
pytest tests/test_performance.py -v --benchmark-only
```

**If end-to-end >100ms:**

1. **Check network latency to exchanges**
   ```bash
   ping -c 10 api.binance.com
   ping -c 10 api.coinbase.com
   ```

2. **Check database query performance**
   ```bash
   docker compose exec postgres psql -U arbitrage -c \
     "SELECT query, mean_exec_time FROM pg_stat_statements
      ORDER BY mean_exec_time DESC LIMIT 10;"
   ```

3. **Check Redis latency**
   ```bash
   docker compose exec redis redis-cli --latency
   ```

4. **Profile Python code**
   ```bash
   python -m cProfile -s cumtime src/main.py > profile.txt
   ```

---

## Security Incidents

### Suspected API Key Compromise

**Immediate Actions:**

1. **Revoke keys immediately** in exchange web UIs
2. **Stop trading**:
   ```bash
   docker compose down
   ```
3. **Generate new keys** with minimum required permissions
4. **Update .env** with new keys
5. **Review audit logs** for unauthorized activity:
   ```bash
   grep "login\|trade\|config" data/audit/audit.log
   ```
6. **Check exchange transaction history** for unauthorized trades

### Unauthorized Access Detected

1. **Change all passwords** immediately
2. **Enable 2FA** on all exchange accounts
3. **Review audit logs**:
   ```bash
   grep "failed\|unauthorized" data/audit/audit.log
   ```
4. **Check for code changes**:
   ```bash
   git log --all --since="24 hours ago"
   git diff HEAD~10
   ```

---

## Escalation Paths

| Issue Severity | Response Time | Contact |
|----------------|---------------|---------|
| Critical (trading losses, security breach) | Immediate | Primary maintainer |
| High (system down, data loss) | <1 hour | On-call engineer |
| Medium (degraded performance) | <4 hours | DevOps team |
| Low (minor issues) | <24 hours | Support queue |

---

## Useful Commands

```bash
# View all logs
make logs

# Restart everything
docker compose restart

# Clean slate restart
docker compose down -v && docker compose up -d

# Check application status
ps aux | grep python | grep main

# Monitor CPU/Memory
docker stats

# Test exchanges
curl https://api.binance.com/api/v3/ping

# Database shell
docker compose exec postgres psql -U arbitrage

# Redis shell
docker compose exec redis redis-cli

# Run tests
make test

# Format code
make format

# Security scan
make security
```

---

**Remember:** When in doubt, STOP TRADING and investigate. Better safe than sorry.

**Last Updated:** 2025-12-17
