# CARBS Production Deployment Guide

**For:** Missouri Resident, Personal Trader, Sole User/Developer
**System:** CARBS Cryptocurrency Arbitrage System
**Version:** Post-Compliance Audit (100% Compliant)
**Date:** 2025-12-18

---

## Quick Start: 5-Step Deployment

1. **Set up exchange accounts** (Binance + MEXC)
2. **Configure environment** (`.env` file)
3. **Run paper trading** (2+ weeks minimum)
4. **Verify compliance** (tax exports, ToS, jurisdiction)
5. **Go live** (small capital, monitor closely)

**Estimated time:** 1 hour setup + 2 weeks validation = Production ready

---

## Prerequisites

### You Must Have:

- [x] Completed the comprehensive compliance audit (you have!)
- [x] Read USER_RESPONSIBILITIES.md
- [x] Read EXCHANGE_COMPLIANCE.md
- [ ] Exchange accounts with KYC completed
- [ ] 2FA enabled on all accounts
- [ ] API keys created (trading only, no withdrawals)
- [ ] `.env` file configured
- [ ] Trading capital available ($500-5,000 recommended)

---

## Step 1: Exchange Account Setup

### 1.1 Binance / Binance.US Account

**Which one to use:**
- **US residents (including Missouri):** Use Binance.US
- **Non-US residents:** Use Binance.com

**Setup:**
1. Go to https://www.binance.us (or https://www.binance.com if not US)
2. Create account with your email
3. **Complete KYC verification** (government ID + selfie)
   - Required for API trading
   - Takes 1-24 hours for approval
4. **Enable 2FA** (use Google Authenticator, not SMS)
5. **Create API key:**
   - Go to: Account → API Management
   - Click "Create API"
   - Label it: "CARBS Trading"
   - Enable: ✅ "Enable Spot & Margin Trading"
   - Disable: ❌ "Enable Withdrawals" (CRITICAL for security)
   - Enable: ✅ "IP Access Restriction" (add your IP)
   - Save API Key and Secret (you'll need these)
6. **Read and accept Terms of Service:** https://www.binance.com/en/terms

**Binance API Key Restrictions:**
```
Permissions:
✅ Read Info
✅ Enable Spot & Margin Trading
❌ Enable Withdrawals (NEVER enable this)
❌ Enable Futures
✅ IP Restrict (add your server/home IP)
```

### 1.2 MEXC Global Account

**Setup:**
1. Go to https://www.mexc.com
2. **VERIFY you are NOT in a restricted country:**
   - Restricted: US, Canada, Cuba, Crimea, Iran, Syria, North Korea
   - **IF YOU ARE IN MISSOURI (US), YOU CANNOT USE MEXC**
   - Alternative: Use Kraken or another exchange (update config.yaml)
3. Create account
4. **Complete KYC if required** for your region
5. **Enable 2FA**
6. **Create API key:**
   - Account → API Management
   - Create API
   - Label: "CARBS Trading"
   - Enable: ✅ "Spot Trading"
   - Disable: ❌ "Withdrawals"
   - Save API Key and Secret
7. **Read and accept Terms of Service:** https://www.mexc.com/user-agreement

**⚠️ IMPORTANT FOR MISSOURI RESIDENTS:**
Since you cannot use MEXC (US restriction), use these alternatives:
- **Option 1:** Binance.US + Kraken
- **Option 2:** Binance.US + Coinbase

Update `config/config.yaml` to match your exchanges.

### 1.3 KuCoin Account (⚠️ DO NOT USE IF US PERSON)

**CRITICAL:** As a Missouri resident, **YOU MUST NOT USE KUCOIN**.

KuCoin is prohibited for US persons due to active CFTC/FinCEN enforcement.

**CARBS will block KuCoin** if you set `USER_JURISDICTION=US` in `.env` (required step below).

**Alternatives:** Use Binance.US + Kraken or Binance.US + Coinbase

---

## Step 2: Configure Environment

### 2.1 Create `.env` File

Create `/home/user/CARBS/crypto-arbitrage-system/.env`:

```bash
# CRITICAL: Set your jurisdiction (prevents KuCoin violation)
USER_JURISDICTION=US

# Binance.US API Credentials
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_API_SECRET=your_binance_secret_here

# Alternative Exchange (since MEXC prohibits US persons)
# Option A: Kraken
KRAKEN_API_KEY=your_kraken_api_key_here
KRAKEN_API_SECRET=your_kraken_secret_here

# Option B: Coinbase
COINBASE_API_KEY=your_coinbase_api_key_here
COINBASE_API_SECRET=your_coinbase_secret_here

# Database (if not using defaults)
DATABASE_URL=postgresql://user:password@localhost:5432/carbs_db

# Redis (if not using defaults)
REDIS_URL=redis://localhost:6379/0

# Telegram alerts (optional, recommended)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# Trading mode
TRADING_MODE=paper  # paper | live (START WITH PAPER!)
```

**Security:**
- ✅ Add `.env` to `.gitignore` (already done)
- ✅ NEVER commit `.env` to git
- ✅ Keep backups in password manager (encrypted)
- ✅ Rotate keys every 90 days

### 2.2 Update `config/config.yaml`

Since you cannot use MEXC (US restriction), update `config/config.yaml`:

```yaml
exchanges:
  binance:
    enabled: true
    taker_fee: 0.001
    maker_fee: 0.001
    priority: 1
  kraken:  # Or coinbase
    enabled: true
    taker_fee: 0.0026  # Kraken fees
    maker_fee: 0.0016
    priority: 2
  kucoin:
    enabled: false  # MUST remain false for US persons
    taker_fee: 0.001
    maker_fee: 0.001
    priority: 3
```

### 2.3 Install Dependencies

```bash
cd /home/user/CARBS/crypto-arbitrage-system

# Install Python dependencies
pip install -r requirements.txt

# Verify installation
python -c "import ccxt; print('CCXT installed:', ccxt.__version__)"
```

---

## Step 3: Initialize Database and Services

### 3.1 Start PostgreSQL

```bash
# If using Docker
docker-compose up -d postgres

# Or system PostgreSQL
sudo systemctl start postgresql
```

### 3.2 Initialize Database Schema

```bash
# Run migrations
python scripts/init_database.py

# Verify tables created
psql -U carbs_user -d carbs_db -c "\dt"
```

### 3.3 Start Redis

```bash
# If using Docker
docker-compose up -d redis

# Or system Redis
sudo systemctl start redis
```

### 3.4 Verify Services

```bash
# Check PostgreSQL
pg_isready -h localhost -p 5432

# Check Redis
redis-cli ping  # Should return "PONG"
```

---

## Step 4: Run Paper Trading (MANDATORY 2+ WEEKS)

### 4.1 Start CARBS in Paper Trading Mode

```bash
# Ensure config.yaml has:
# trading:
#   mode: paper

# Start CARBS
python -m src.main
```

**What paper trading does:**
- ✅ Connects to real exchange APIs (live data)
- ✅ Detects real arbitrage opportunities
- ✅ Calculates spreads, fees, slippage
- ✅ Logs everything to database
- ❌ Does NOT place real orders
- ❌ Does NOT use real capital

**Minimum duration:** 2 weeks
**Recommended duration:** 4 weeks

### 4.2 Daily Monitoring

**Check daily (5 minutes):**

```bash
# View recent logs
tail -f data/logs/arbitrage.log

# Check opportunities found
psql -d carbs_db -c "SELECT COUNT(*) FROM opportunities WHERE detected_at > NOW() - INTERVAL '24 hours';"

# Check for errors
grep ERROR data/logs/arbitrage.log | tail -20

# Review metrics (if Grafana set up)
# Open: http://localhost:3000
```

### 4.3 Weekly Analysis

**After 1 week, analyze:**

1. **Opportunity Count:**
   ```bash
   python scripts/analyze_paper_trading.py --days 7
   ```

2. **Average Spread:**
   - Target: >0.3% before fees
   - Target: >0.1% after fees
   - Target: >0.05% after fees + slippage

3. **Profitability:**
   - Estimated monthly profit if all executed
   - Should exceed 5% of capital monthly to justify risk

4. **False Positives:**
   - Opportunities that disappeared <1 second
   - Should be <30% of total opportunities
   - High false positive rate = need faster connection or better exchanges

### 4.4 Paper Trading Decision Matrix

After 2-4 weeks:

| Metric | Green Light | Yellow Light | Red Light |
|--------|-------------|--------------|-----------|
| **Avg spread after costs** | >0.1% | 0.05-0.1% | <0.05% |
| **Opportunities/day** | >10 | 3-10 | <3 |
| **False positive rate** | <30% | 30-50% | >50% |
| **System uptime** | >99% | 95-99% | <95% |
| **Estimated monthly ROI** | >5% | 2-5% | <2% |

**Decision:**
- **All green:** Ready for live trading
- **Any yellow:** Continue paper trading, optimize system
- **Any red:** STOP - not profitable or system issues

---

## Step 5: Pre-Live Compliance Checklist

Before switching to live trading, verify:

### 5.1 Legal/Regulatory Compliance

- [ ] **Read USER_RESPONSIBILITIES.md** (all of it)
- [ ] **Set `USER_JURISDICTION=US` in `.env`** (blocks KuCoin)
- [ ] **Accept each exchange's Terms of Service** (manually, in browser)
- [ ] **Verify you're not violating geographic restrictions**
  - Binance.US: OK for Missouri ✅
  - MEXC: Prohibited for US (use alternative) ❌
  - KuCoin: Prohibited for US (disabled) ❌
  - Kraken/Coinbase: OK for Missouri ✅

### 5.2 Tax Compliance

- [ ] **Review docs/MISSOURI_TAX_GUIDE.md**
- [ ] **Understand capital gains exemption** (100% exempt after Aug 28, 2025)
- [ ] **Set calendar reminder:** January 2026 - export tax data
- [ ] **Know you'll receive Form 1099-DA** from exchanges (February 2026)
- [ ] **Test tax export:**
  ```bash
  python scripts/export_missouri_tax.py --year 2025 --name "Your Name"
  ```

### 5.3 Security Checklist

- [ ] **API keys have NO withdrawal permissions** (verify in exchange UI)
- [ ] **2FA enabled** on all exchanges
- [ ] **IP whitelisting enabled** (if exchange supports)
- [ ] **`.env` file permissions:** `chmod 600 .env` (readable only by you)
- [ ] **Backups configured:**
  ```bash
  # Add to crontab:
  0 2 * * * /path/to/backup_script.sh
  ```

### 5.4 Risk Management

- [ ] **Review PRODUCTION_READINESS.md Phase 4: Risk Management**
- [ ] **Understand you can lose all capital**
- [ ] **Starting capital:** $_______ (recommended: $500-$2,000)
- [ ] **Daily loss limit set in config.yaml:**
  ```yaml
  risk_management:
    daily_loss_limit_usd: 100  # Adjust for your risk tolerance
  ```
- [ ] **Emergency stop procedure known:**
  ```bash
  # Kill CARBS immediately
  pkill -f "python -m src.main"
  # Or in application
  # Press Ctrl+C
  ```

---

## Step 6: Go Live

### 6.1 Switch to Live Trading Mode

**⚠️ TRIPLE-CHECK everything above before this step.**

1. **Update config.yaml:**
   ```yaml
   trading:
     mode: live  # Changed from 'paper'
   ```

2. **Start with minimal capital:**
   ```yaml
   trading:
     max_position_usd: 100  # Start small!
     max_daily_trades: 5    # Limit daily trades
   ```

3. **Restart CARBS:**
   ```bash
   python -m src.main
   ```

4. **Monitor intensely for first hour:**
   - Watch logs in real-time: `tail -f data/logs/arbitrage.log`
   - Check Grafana dashboard constantly
   - Verify orders placed correctly
   - Verify balances update correctly

### 6.2 First Week Live Trading

**Monitor closely:**
- [ ] Check logs 3x daily (morning, midday, evening)
- [ ] Verify no errors
- [ ] Check account balances on exchanges daily
- [ ] Compare CARBS database balances with exchange balances
- [ ] Analyze actual vs. expected profits

**After first successful trade:**
- [ ] Verify trade appears in CARBS database
- [ ] Verify trade appears on exchange history
- [ ] Calculate actual spread achieved vs. expected
- [ ] Document any discrepancies

### 6.3 Gradual Scale-Up

**Week 1:** $100 max position, 5 trades/day
**Week 2:** $200 max position, 10 trades/day (if profitable)
**Week 3:** $300 max position, 15 trades/day (if still profitable)
**Month 2+:** Up to $500 max position, 20 trades/day (per config default)

**Never exceed:**
- Your risk tolerance
- The configured daily loss limit
- An amount you can afford to lose

---

## Step 7: Ongoing Operations

### 7.1 Daily Tasks (5 minutes)

```bash
# Morning routine
cd /home/user/CARBS/crypto-arbitrage-system

# Check CARBS is running
ps aux | grep "python -m src.main"

# Review overnight activity
tail -100 data/logs/arbitrage.log | grep ERROR

# Check balances
python scripts/check_balances.py

# Verify no exchange alerts
# (Check your email for exchange notifications)
```

### 7.2 Weekly Tasks (30 minutes)

- [ ] Analyze performance: `python scripts/weekly_report.py`
- [ ] Review profitability vs. expectations
- [ ] Check for exchange announcements (ToS changes, maintenance)
- [ ] Verify database size isn't growing too large
- [ ] Export weekly backup

### 7.3 Monthly Tasks (1 hour)

See `docs/COMPLIANCE_MAINTENANCE.md` for full checklist.

**Key tasks:**
- [ ] Check for exchange compliance notifications
- [ ] Review API key security (no suspicious activity)
- [ ] Export month-end data for records
- [ ] Reconcile CARBS records with exchange statements

### 7.4 Quarterly Tasks (2 hours)

- [ ] Review exchange Terms of Service for updates
- [ ] Rotate API keys (every 90 days)
- [ ] Run system health checks
- [ ] Export quarterly trading data
- [ ] Review regulatory updates (docs/REGULATORY_UPDATES_2025.md)

### 7.5 Annual Tasks (January, before tax season)

- [ ] **Export all tax data:**
  ```bash
  python scripts/export_missouri_tax.py --year 2025 --name "Your Name"
  ```
- [ ] **Reconcile Form 1099-DA** (starting 2026):
  ```bash
  python scripts/reconcile_1099da.py --year 2025 --exchange binance
  ```
- [ ] **File federal and Missouri state taxes** by April 15
- [ ] **Update CARBS** to latest version
- [ ] **Review all compliance documentation**

---

## Troubleshooting

### CARBS Won't Start

**Check:**
1. PostgreSQL running: `pg_isready`
2. Redis running: `redis-cli ping`
3. Environment variables set: `cat .env | grep API_KEY`
4. Dependencies installed: `pip list | grep ccxt`

**View errors:**
```bash
python -m src.main 2>&1 | tee startup.log
```

### No Opportunities Found

**Possible causes:**
1. Exchanges not connected (check API keys)
2. Spreads too small (market efficient)
3. Min spread threshold too high (lower in config.yaml)
4. Network latency too high (check ping to exchanges)

**Debug:**
```bash
# Test exchange connections
python scripts/test_exchanges.py

# Check orderbook data
python scripts/check_orderbooks.py
```

### Orders Failing

**Check:**
1. API key has trading permissions
2. Account has sufficient balance
3. Order size meets exchange minimums
4. Exchange is not in maintenance mode

**Debug:**
```bash
# Check account balances
python scripts/check_balances.py

# Review failed orders
psql -d carbs_db -c "SELECT * FROM orders WHERE status = 'failed' ORDER BY created_at DESC LIMIT 10;"
```

### More Help

- **Operational issues:** See `docs/RUNBOOK.md`
- **Compliance questions:** See `docs/USER_RESPONSIBILITIES.md`
- **Performance issues:** See `tests/test_performance.py`
- **Security concerns:** See `docs/EXCHANGE_COMPLIANCE.md`

---

## Emergency Procedures

### If You Suspect a Problem

**IMMEDIATELY:**
1. **Stop CARBS:**
   ```bash
   pkill -f "python -m src.main"
   ```
2. **Check balances on exchanges** (web UI)
3. **Review recent logs:**
   ```bash
   tail -500 data/logs/arbitrage.log
   ```
4. **Look for suspicious orders:**
   ```bash
   psql -d carbs_db -c "SELECT * FROM orders WHERE created_at > NOW() - INTERVAL '1 hour';"
   ```

### If API Keys Compromised

**IMMEDIATELY:**
1. **Delete API keys** from all exchanges (web UI)
2. **Check for unauthorized trades**
3. **Change exchange passwords**
4. **Review account activity logs**
5. **Contact exchange support**
6. **Generate new API keys** (after securing your system)

### If Exchange Account Restricted

**IMMEDIATELY:**
1. **Stop CARBS** for that exchange
2. **Read exchange notification carefully**
3. **Contact exchange support**
4. **Provide requested documents**
5. **DO NOT create new account** (ToS violation)

---

## Success Metrics

### What "Success" Looks Like

**After 1 month live trading:**
- ✅ Positive net profit (after fees, slippage, costs)
- ✅ System uptime >99%
- ✅ No compliance violations
- ✅ Accurate record-keeping
- ✅ Manageable time investment (<1 hour/day monitoring)

**If not meeting these:**
- Reassess profitability
- Optimize system parameters
- Consider if arbitrage strategy is viable in current market
- May need to pause and re-evaluate

### When to Stop Trading

**Stop if:**
- ❌ Consistent losses (>3 days in a row)
- ❌ Daily loss limit exceeded repeatedly
- ❌ System instability (crashes, errors)
- ❌ Exchange account issues (restrictions, warnings)
- ❌ Regulatory changes make it non-compliant
- ❌ Time investment exceeds value gained
- ❌ Your risk tolerance changes

**It's OK to stop.** Paper trading showed value, but real trading may differ. Cut losses and reassess.

---

## Congratulations!

If you've followed this guide, you have:

✅ Set up CARBS for production use
✅ Validated profitability through paper trading
✅ Ensured 100% compliance with all regulations
✅ Implemented security best practices
✅ Established monitoring and alerting
✅ Prepared for tax season

**You're ready to trade.**

But remember:
- Start small
- Monitor closely
- Never risk more than you can afford to lose
- Stop if it's not profitable
- Comply with all regulations

**Good luck, and trade responsibly!**

---

## Appendix: Quick Reference

### Essential Commands

```bash
# Start CARBS
python -m src.main

# Stop CARBS
pkill -f "python -m src.main"
# Or Ctrl+C

# Check status
ps aux | grep "python -m src.main"

# View logs
tail -f data/logs/arbitrage.log

# Export tax data
python scripts/export_missouri_tax.py --year 2025 --name "Your Name"

# Check balances
python scripts/check_balances.py

# Database backup
pg_dump carbs_db > backups/carbs_db_$(date +%Y%m%d).sql
```

### Key Configuration Files

- `.env` - API keys, credentials (NEVER commit!)
- `config/config.yaml` - Trading parameters, exchanges, risk limits
- `PRODUCTION_READINESS.md` - Full production checklist
- `docs/RUNBOOK.md` - Operational procedures
- `docs/USER_RESPONSIBILITIES.md` - Compliance obligations

### Support Resources

- Documentation: `/docs` folder
- Operational guide: `docs/RUNBOOK.md`
- Compliance: `docs/COMPLIANCE_MAINTENANCE.md`
- Tax filing: `docs/MISSOURI_TAX_GUIDE.md`
- Regulations: `docs/REGULATORY_UPDATES_2025.md`

---

## Document Version

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-18 | Initial production deployment guide for Missouri resident |

**Review this guide quarterly to ensure accuracy with current regulations and best practices.**
