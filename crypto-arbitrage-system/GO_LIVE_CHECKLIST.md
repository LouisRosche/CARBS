# CARBS Go-Live Checklist
**Final Pre-Production Verification**

**Date:** _____________
**Completed by:** _____________
**Trading Capital:** $_____________

---

## ⚠️ CRITICAL: READ FIRST

**DO NOT proceed with live trading until ALL checkboxes are checked.**

This checklist ensures you've completed the comprehensive compliance audit, understand all risks, and have properly configured CARBS for production use.

**Total estimated time:** 2-4 weeks (including mandatory paper trading)

---

## Phase 1: Documentation Review (30 minutes)

**Read and understand these documents:**

- [ ] ✅ `docs/USER_RESPONSIBILITIES.md` - Your compliance obligations
- [ ] ✅ `docs/EXCHANGE_COMPLIANCE.md` - Exchange ToS requirements
- [ ] ✅ `docs/EXCHANGE_TOS_COMPLIANCE_ANALYSIS.md` - Trading pattern compliance
- [ ] ✅ `docs/MISSOURI_TAX_GUIDE.md` - Missouri tax rules (if MO resident)
- [ ] ✅ `crypto-arbitrage-system/COMPLIANCE_AUDIT_REPORT.md` - Legal/regulatory compliance
- [ ] ✅ `docs/REGULATORY_UPDATES_2025.md` - 2025 regulatory changes (Form 1099-DA!)
- [ ] ✅ `docs/PRODUCTION_DEPLOYMENT_GUIDE.md` - Deployment steps
- [ ] ✅ `PRODUCTION_READINESS.md` - Full production checklist
- [ ] ✅ `docs/RUNBOOK.md` - Operational procedures
- [ ] ✅ `README.md` - System overview and risk warnings

**Certification:**
I have read and understood all documentation above.

Signature: _________________ Date: _____________

---

## Phase 2: Legal & Regulatory Compliance (1 hour)

### 2.1 Jurisdiction Setup

- [ ] **Set `USER_JURISDICTION=US` in `.env` file** (if US person)
  ```bash
  echo "USER_JURISDICTION=US" >> .env
  ```
- [ ] **Verified this blocks KuCoin** (test by trying to initialize KuCoin - should fail)
- [ ] **Understand KuCoin is prohibited for US persons** (CFTC/FinCEN enforcement)

### 2.2 Exchange Terms of Service

- [ ] **Read Binance/Binance.US Terms of Service:**
  - URL: https://www.binance.com/en/terms (or .us)
  - **Accepted in browser:** ☐ Yes  ☐ No
  - Date accepted: _____________

- [ ] **Read Alternative Exchange ToS** (Kraken or Coinbase):
  - Exchange: _____________
  - URL: _____________
  - **Accepted in browser:** ☐ Yes  ☐ No
  - Date accepted: _____________

- [ ] **Understand MEXC is prohibited for US persons** (use Kraken/Coinbase instead)

- [ ] **Verified I'm not in a restricted jurisdiction** for each exchange

### 2.3 Tax Compliance Understanding

- [ ] **Understand I must report ALL crypto income to IRS** (even if no 1099 received)
- [ ] **Understand Missouri capital gains exemption:**
  - Before Aug 28, 2025: Regular tax rates apply
  - After Aug 28, 2025: 100% exempt
  - Still must report even if exempt
- [ ] **Set calendar reminder:** January 2026 - Export tax data
- [ ] **Know I'll receive Form 1099-DA** from exchanges (by Feb 17, 2026)
- [ ] **Tested CARBS tax export:**
  ```bash
  python scripts/export_missouri_tax.py --year 2025 --name "Test"
  ```
  Result: ☐ Success  ☐ Failed

### 2.4 Compliance Maintenance

- [ ] **Set quarterly calendar reminders** (Jan 15, Apr 15, Jul 15, Oct 15):
  - Review exchange ToS for changes
  - Rotate API keys (every 90 days)
  - Run system health checks
  - Export transaction history from exchanges

---

## Phase 3: Exchange Account Setup (2-4 hours + KYC approval time)

### 3.1 Binance / Binance.US

- [ ] **Account created:** ☐ Binance.com  ☐ Binance.US
- [ ] **Email verified**
- [ ] **KYC verification completed:**
  - Status: ☐ Approved  ☐ Pending  ☐ Not started
  - Date approved: _____________
- [ ] **2FA enabled:** ☐ Authenticator app  ☐ SMS (not recommended)
- [ ] **API key created:**
  - Key created date: _____________
  - Label: "CARBS Trading"
  - ✅ **Trading enabled**
  - ❌ **Withdrawals DISABLED** (verify in UI!)
  - ✅ **IP whitelist enabled** (if available)
  - IP whitelisted: _____________
- [ ] **API key and secret saved** in password manager (encrypted)
- [ ] **Funded account with trading capital:** $_____________

### 3.2 Alternative Exchange (Kraken or Coinbase)

**Exchange:** ☐ Kraken  ☐ Coinbase  ☐ Other: _____________

- [ ] **Account created**
- [ ] **Email verified**
- [ ] **KYC verification completed:**
  - Status: ☐ Approved  ☐ Pending  ☐ Not started
  - Date approved: _____________
- [ ] **2FA enabled:** ☐ Authenticator app  ☐ SMS (not recommended)
- [ ] **API key created:**
  - Key created date: _____________
  - Label: "CARBS Trading"
  - ✅ **Trading enabled**
  - ❌ **Withdrawals DISABLED**
  - ✅ **IP whitelist enabled** (if available)
  - IP whitelisted: _____________
- [ ] **API key and secret saved** in password manager
- [ ] **Funded account with trading capital:** $_____________

### 3.3 Account Verification

- [ ] **Tested login to each exchange** (no restrictions or warnings)
- [ ] **No pending compliance requests** from exchanges
- [ ] **Trading permissions active** (spot trading enabled)
- [ ] **Account standing: GOOD** (no warnings, restrictions, or limits)

---

## Phase 4: CARBS Configuration (1 hour)

### 4.1 Environment Setup

- [ ] **Created `.env` file** in `/home/user/CARBS/crypto-arbitrage-system/`
- [ ] **Added to `.env`:**
  ```bash
  USER_JURISDICTION=US
  BINANCE_API_KEY=<your_key>
  BINANCE_API_SECRET=<your_secret>
  KRAKEN_API_KEY=<your_key>     # Or COINBASE_API_KEY
  KRAKEN_API_SECRET=<your_secret>  # Or COINBASE_API_SECRET
  TRADING_MODE=paper  # Start with paper trading!
  ```
- [ ] **Set file permissions:** `chmod 600 .env` (readable only by you)
- [ ] **Verified `.env` in `.gitignore`** (not committed to git)

### 4.2 Config File Updates

- [ ] **Updated `config/config.yaml` exchanges section:**
  ```yaml
  exchanges:
    binance:
      enabled: true
      taker_fee: 0.001
      maker_fee: 0.001
      priority: 1
    kraken:  # Or coinbase
      enabled: true
      taker_fee: 0.0026  # Adjust for your exchange
      maker_fee: 0.0016
      priority: 2
    kucoin:
      enabled: false  # MUST stay false for US persons
  ```

- [ ] **Set conservative risk limits:**
  ```yaml
  trading:
    mode: paper  # Start with paper!
    min_spread_percent: 0.3
    max_position_usd: 100  # Start small!
    max_daily_trades: 5    # Limit trades initially
    max_daily_loss_usd: 50
  ```

### 4.3 Database and Services

- [ ] **PostgreSQL running:** `pg_isready` returns success
- [ ] **Redis running:** `redis-cli ping` returns "PONG"
- [ ] **Database schema initialized:** `python scripts/init_database.py`
- [ ] **Verified tables created:** `psql -d carbs_db -c "\dt"`

### 4.4 Dependency Installation

- [ ] **Installed Python dependencies:** `pip install -r requirements.txt`
- [ ] **Verified CCXT installed:** `python -c "import ccxt; print(ccxt.__version__)"`
- [ ] **No import errors:** `python -m src.main --version` (or equivalent test)

---

## Phase 5: Paper Trading Validation (MANDATORY 2+ weeks)

### 5.1 Start Paper Trading

- [ ] **Confirmed `trading.mode: paper` in config.yaml**
- [ ] **Started CARBS:** `python -m src.main`
- [ ] **No errors on startup** (check logs)
- [ ] **Connected to exchanges successfully** (check logs)
- [ ] **Start date:** _____________

### 5.2 Week 1-2: System Stability

- [ ] **System ran continuously for 2 weeks** without crashes
- [ ] **No critical errors** in `data/logs/arbitrage.log`
- [ ] **Opportunities detected** (check database or Grafana)
  - Total opportunities found: _____________
- [ ] **All exchanges connecting** successfully
- [ ] **Database storing data** correctly
- [ ] **Redis cache functioning** properly

### 5.3 Week 3-4: Profitability Analysis

- [ ] **Analyzed paper trading results:**
  ```bash
  python scripts/analyze_paper_trading.py --days 14
  ```

**Record metrics:**
- Total opportunities: _____________
- Average spread (before fees): ______________%
- Average spread (after fees): ______________%
- Average spread (after fees + slippage): ______________%
- Winning percentage (positive net spread): ______________%
- False positive rate: ______________%
- Estimated monthly profit (if all executed): $_____________
- System uptime: ______________%

### 5.4 Paper Trading Decision

Using the decision matrix from PRODUCTION_READINESS.md:

| Metric | Your Value | Status |
|--------|------------|--------|
| Avg spread after costs | _______% | ☐ Green (>0.1%)  ☐ Yellow (0.05-0.1%)  ☐ Red (<0.05%) |
| Opportunities/day | _______ | ☐ Green (>10)  ☐ Yellow (3-10)  ☐ Red (<3) |
| False positive rate | _______% | ☐ Green (<30%)  ☐ Yellow (30-50%)  ☐ Red (>50%) |
| System uptime | _______% | ☐ Green (>99%)  ☐ Yellow (95-99%)  ☐ Red (<95%) |
| Estimated monthly ROI | _______% | ☐ Green (>5%)  ☐ Yellow (2-5%)  ☐ Red (<2%) |

**Decision:**
- ☐ **All green:** Ready for live trading (proceed to Phase 6)
- ☐ **Any yellow:** Continue paper trading, optimize system (STOP HERE)
- ☐ **Any red:** Not profitable or system issues (DO NOT GO LIVE)

**If not all green, DO NOT proceed to Phase 6.**

---

## Phase 6: Pre-Live Security Audit (30 minutes)

### 6.1 API Key Security

- [ ] **Binance API key restrictions verified:**
  - Go to Binance → API Management → View key
  - ✅ Spot Trading: Enabled
  - ❌ Withdrawals: **DISABLED**
  - ✅ IP Restriction: Enabled (if available)

- [ ] **Alternative exchange API key restrictions verified:**
  - ✅ Trading: Enabled
  - ❌ Withdrawals: **DISABLED**
  - ✅ IP Restriction: Enabled (if available)

- [ ] **API keys backed up** in encrypted password manager
- [ ] **API keys NOT in git** (`.env` in `.gitignore`)

### 6.2 System Security

- [ ] **`.env` file permissions:** `chmod 600 .env`
- [ ] **2FA enabled** on all exchanges
- [ ] **Strong, unique passwords** for each exchange
- [ ] **Password manager** in use (1Password, Bitwarden, LastPass)
- [ ] **OS security updates installed**
- [ ] **Antivirus/antimalware active** (if applicable)
- [ ] **Firewall enabled**

### 6.3 Backup and Disaster Recovery

- [ ] **Database backup script created:**
  ```bash
  #!/bin/bash
  pg_dump carbs_db > backups/carbs_db_$(date +%Y%m%d).sql
  gzip backups/carbs_db_$(date +%Y%m%d).sql
  ```
- [ ] **Backup script added to crontab:** `crontab -e`
  ```
  0 2 * * * /path/to/backup_script.sh
  ```
- [ ] **Tested backup restore:**
  ```bash
  createdb carbs_db_test
  psql carbs_db_test < backups/carbs_db_YYYYMMDD.sql
  ```
  Result: ☐ Success  ☐ Failed

- [ ] **Know emergency stop procedure:**
  ```bash
  pkill -f "python -m src.main"
  ```

---

## Phase 7: Risk Management (15 minutes)

### 7.1 Risk Acknowledgment

**I understand and accept:**

- [ ] **Cryptocurrency trading can result in 100% loss of capital**
- [ ] **This software has NO guarantees of profit**
- [ ] **I am responsible for all trading outcomes**
- [ ] **I should only trade with capital I can afford to lose**
- [ ] **Arbitrage opportunities may be rare and unprofitable**
- [ ] **Exchanges can freeze accounts or change rules**
- [ ] **Regulatory changes could affect trading**
- [ ] **I may need to stop trading if unprofitable**

### 7.2 Capital and Limits

- [ ] **Starting trading capital:** $_____________
- [ ] **I can afford to lose this entire amount:** ☐ Yes  ☐ No
- [ ] **Daily loss limit set in config.yaml:** $_____________
- [ ] **Position size limit set:** $_____________
- [ ] **Daily trade limit set:** _____________

**If "No" to afford to lose, DO NOT GO LIVE.**

### 7.3 Monitoring Plan

- [ ] **Committed to daily monitoring:** ☐ Yes  ☐ No (required!)
- [ ] **Time available:** _______ minutes/day (minimum 5 minutes)
- [ ] **Set calendar reminders:**
  - Daily: Check logs and balances (5 min)
  - Weekly: Analyze performance (30 min)
  - Monthly: Full review (1 hour)
  - Quarterly: Compliance review (2 hours)

---

## Phase 8: Final Go-Live Checks (10 minutes)

### 8.1 System Final Verification

- [ ] **Paper trading completed:** ☐ 2 weeks  ☐ 4 weeks
- [ ] **Paper trading metrics met "green light" criteria**
- [ ] **All compliance documentation read and understood**
- [ ] **All security measures implemented**
- [ ] **Backup and disaster recovery tested**
- [ ] **Risk limits configured conservatively**

### 8.2 Pre-Live Checklist

- [ ] **PostgreSQL running**
- [ ] **Redis running**
- [ ] **API keys valid and restricted properly**
- [ ] **`.env` file configured correctly**
- [ ] **`config.yaml` updated for your exchanges**
- [ ] **Backups automated**
- [ ] **Emergency procedures known**

### 8.3 Switch to Live Mode

**⚠️ FINAL WARNING: ONLY proceed if ALL above boxes are checked.**

- [ ] **Updated `config.yaml`:**
  ```yaml
  trading:
    mode: live  # Changed from 'paper'
    max_position_usd: 100  # Start VERY small
    max_daily_trades: 5    # Limit initially
  ```

- [ ] **Restarted CARBS:**
  ```bash
  pkill -f "python -m src.main"  # Stop paper trading
  python -m src.main              # Start live trading
  ```

- [ ] **Verified "LIVE TRADING MODE" in logs**
- [ ] **Go-live date/time:** _____________ _____________

---

## Phase 9: First Hour Live Monitoring (CRITICAL)

### 9.1 Intense Monitoring

**Watch constantly for first hour:**

- [ ] **Logs monitoring:** `tail -f data/logs/arbitrage.log`
- [ ] **No errors** in logs
- [ ] **Opportunities detected** (if market conditions allow)
- [ ] **Orders placed correctly** (if opportunity arises)
- [ ] **Balances updating** correctly
- [ ] **No unexpected behavior**

### 9.2 First Trade Verification

**When first trade executes:**

- [ ] **Trade appears in CARBS database:**
  ```bash
  psql -d carbs_db -c "SELECT * FROM trades ORDER BY executed_at DESC LIMIT 1;"
  ```
- [ ] **Trade appears on exchange history** (web UI)
- [ ] **Spread achieved vs. expected:** _______% vs. _______%
- [ ] **Profit/loss:** $_______ (actual) vs. $_______ (expected)
- [ ] **Any discrepancies:** _____________________________________________

**If major discrepancies (>50% difference), STOP and investigate.**

---

## Phase 10: First Week Live Operations

### 10.1 Daily Checks (First Week)

Monitor 3x daily (morning, midday, evening):

**Day 1:**
- [ ] Morning: System running, no errors
- [ ] Midday: Balances correct
- [ ] Evening: Review day's activity

**Day 2-7:** (repeat daily)
- [ ] Check logs for errors
- [ ] Verify balances on exchanges match CARBS database
- [ ] Review any trades executed
- [ ] Calculate actual vs. expected profits
- [ ] Document any issues

### 10.2 End of Week 1 Review

**Metrics:**
- Total trades executed: _____________
- Total profit/loss: $_____________
- Average profit per trade: $_____________
- Actual spread vs. paper trading: _______% vs. _______%
- System uptime: _______%
- Issues encountered: _____________

**Decision:**
- ☐ **Profitable and stable:** Continue, consider gradual scale-up
- ☐ **Unprofitable:** Stop and reassess
- ☐ **Technical issues:** Pause, fix issues, resume
- ☐ **Compliance concerns:** Stop immediately, resolve

---

## Phase 11: Scale-Up Plan (If Profitable)

### 11.1 Gradual Increase

**Only if Week 1 was profitable and stable:**

- [ ] **Week 2:**
  - Increase `max_position_usd` to $200
  - Increase `max_daily_trades` to 10
  - Continue monitoring daily

- [ ] **Week 3:**
  - Increase `max_position_usd` to $300
  - Increase `max_daily_trades` to 15
  - Continue monitoring daily

- [ ] **Month 2+:**
  - Increase `max_position_usd` to $500 (or config default)
  - Increase `max_daily_trades` to 20
  - Reduce monitoring to weekly (daily checks still recommended)

**NEVER exceed:**
- Your risk tolerance
- Configured daily loss limit
- An amount you can afford to lose

---

## Congratulations! 🎉

If you've reached this point and checked ALL boxes above, you have:

✅ Completed comprehensive compliance audit
✅ Set up exchanges properly with 2FA and restricted API keys
✅ Configured CARBS correctly
✅ Validated profitability through paper trading
✅ Implemented security best practices
✅ Prepared for tax compliance
✅ Gone live responsibly with small capital
✅ Monitored intensely during first operations

**You're now running a production-ready, 100% compliant cryptocurrency arbitrage system.**

---

## Ongoing Responsibilities

**Remember to:**

✅ **Daily** (5 min): Check logs, verify system running, check balances
✅ **Weekly** (30 min): Analyze performance, export backup
✅ **Monthly** (1 hour): Full review, reconcile with exchange statements
✅ **Quarterly** (2 hours): ToS review, API key rotation, compliance check
✅ **Annually** (4 hours): Tax export, Form 1099-DA reconciliation, file taxes

**See `docs/COMPLIANCE_MAINTENANCE.md` for detailed ongoing tasks.**

---

## Final Certifications

### I certify that:

- ☑ I have completed ALL items on this checklist
- ☑ I have read and understood all required documentation
- ☑ I understand all risks involved in cryptocurrency trading
- ☑ I accept full responsibility for trading outcomes
- ☑ I will comply with all legal and regulatory requirements
- ☑ I will monitor the system daily
- ☑ I will stop trading if it becomes unprofitable
- ☑ I understand CARBS provides no guarantees

**Signature:** _________________

**Date:** _________________

**Witness (optional):** _________________

---

## Emergency Contacts

**If you need help:**

**Technical Issues:**
- Review: `docs/RUNBOOK.md`
- Logs: `data/logs/arbitrage.log`

**Compliance Questions:**
- CPA: _________________ (phone: _____________)
- Attorney: _________________ (phone: _____________)

**Exchange Support:**
- Binance: https://www.binance.com/en/support
- Kraken: https://support.kraken.com
- Coinbase: https://help.coinbase.com

**Emergency Stop:**
```bash
pkill -f "python -m src.main"
```

---

## Document Version

| Version | Date | Author |
|---------|------|--------|
| 1.0 | 2025-12-18 | CARBS Compliance Team |

**This checklist should be completed before every production deployment.**

**Save this completed checklist for your records (7 years for tax audit defense).**
