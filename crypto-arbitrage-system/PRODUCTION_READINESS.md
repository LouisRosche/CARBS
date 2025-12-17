# Production Readiness Checklist

**⚠️ DO NOT skip any items on this checklist before live trading with real capital.**

This checklist ensures you have properly validated CARBS for production use and understand the risks involved.

---

## ⛔ CRITICAL: Before You Begin

**Cryptocurrency trading can result in total loss of capital. Only proceed if:**

- [ ] You fully understand arbitrage trading mechanics
- [ ] You can afford to lose 100% of your trading capital
- [ ] You have consulted with a financial advisor (if uncertain)
- [ ] You understand this software has NO guarantees
- [ ] You accept FULL responsibility for all trading outcomes

**If you cannot check ALL boxes above, DO NOT proceed with live trading.**

---

## Phase 1: Paper Trading Validation (MANDATORY)

**Duration: Minimum 2 weeks, Recommended 4 weeks**

### Week 1-2: Initial Validation

- [ ] **System runs continuously for 2+ weeks** without crashes
- [ ] **No critical errors** in logs (check `data/logs/` daily)
- [ ] **Opportunities detected** regularly (check dashboard and Grafana)
- [ ] **Spread calculations accurate** (manually verify 10+ opportunities)
- [ ] **All exchanges connect** successfully (Binance, Coinbase, Kraken, etc.)
- [ ] **Database persists data** correctly (check PostgreSQL tables)
- [ ] **Redis cache functions** properly (check cache hit rates in metrics)

### Week 3-4: Profitability Analysis

- [ ] **Total opportunities found:** _______ (track in spreadsheet)
- [ ] **Average spread:** _______% (before fees)
- [ ] **Average spread after fees:** _______% (critical metric)
- [ ] **Average spread after fees + slippage:** _______% (must be positive)
- [ ] **Estimated monthly profit** (if all opportunities executed): $______
- [ ] **Winning percentage:** _______% (opportunities with positive net spread)
- [ ] **False positives identified:** _______ (opportunities that disappeared before execution)

**DECISION POINT:**
- If average spread after fees + slippage < 0.2%, **STOP** — Not profitable
- If false positive rate > 50%, **STOP** — Too much latency or data quality issues
- If estimated monthly profit < (capital * 0.05), **RECONSIDER** — Low ROI vs. risk

---

## Phase 2: Technical Validation

### Infrastructure

- [ ] **PostgreSQL database** configured for production (see DEPLOYMENT.md)
  - [ ] Connection pooling enabled
  - [ ] Backups automated (daily minimum)
  - [ ] Disk space monitored (alerts at 80% usage)
  - [ ] TimescaleDB compression configured

- [ ] **Redis cache** optimized
  - [ ] Maxmemory policy set (e.g., `allkeys-lru`)
  - [ ] Persistence configured (RDB or AOF)
  - [ ] Memory alerts configured

- [ ] **Monitoring stack** operational
  - [ ] Prometheus scraping metrics
  - [ ] Grafana dashboards accessible
  - [ ] Alertmanager routing configured (email, Telegram, Slack, PagerDuty)
  - [ ] Critical alerts tested (send test alert and verify receipt)

### Performance Validation

- [ ] **Latency benchmarks pass** (run `pytest tests/test_performance.py`)
  - [ ] End-to-end opportunity detection: <100ms ✅
  - [ ] Orderbook processing: <10ms ✅
  - [ ] Spread calculation: <1ms ✅
  - [ ] Slippage estimation: <5ms ✅

- [ ] **Network latency measured** to each exchange
  - [ ] Binance: ____ms average
  - [ ] Coinbase: ____ms average
  - [ ] Kraken: ____ms average
  - [ ] All exchanges: <50ms average (recommended)

- [ ] **System uptime** > 99.5% during paper trading period

### Security Audit

- [ ] **API keys configured** with minimum required permissions
  - [ ] Binance: Spot trading only, NO withdrawal permissions
  - [ ] Coinbase: Trading only, NO withdrawal permissions
  - [ ] Kraken: Trading only, NO withdrawal permissions
  - [ ] Verify each exchange's key restrictions in web UI

- [ ] **IP whitelisting** enabled (if exchange supports it)
  - [ ] Binance: Configured ✅
  - [ ] Coinbase: Configured ✅ (if supported)
  - [ ] Other exchanges: Configured ✅

- [ ] **Master encryption key** set via environment variable
  - [ ] NOT in .env file
  - [ ] Generated with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
  - [ ] Stored securely (password manager, secrets vault)

- [ ] **.env file permissions** restricted
  ```bash
  chmod 600 .env
  ls -la .env  # Should show: -rw------- (600)
  ```

- [ ] **No secrets in git history**
  ```bash
  git log --all --full-history --source -- .env
  # Should return nothing
  ```

- [ ] **Security scans pass**
  - [ ] `bandit -r src/` (no high-severity issues)
  - [ ] `safety check -r requirements.txt` (no known vulnerabilities)

- [ ] **Audit logging enabled**
  - [ ] Logs writing to `data/audit/audit.log`
  - [ ] Log rotation working (check for `audit_*.log.gz` files)
  - [ ] Audit integrity verified: `python -c "from security.audit import get_audit_logger; print(get_audit_logger().verify_integrity())"`

### Risk Management Configuration

- [ ] **Position size limits** configured conservatively
  - [ ] `max_position_usd` in config.yaml: $_______ (recommend: $100-500 for first month)
  - [ ] Never more than 5% of total trading capital per position

- [ ] **Minimum spread** set appropriately
  - [ ] `min_spread_percent` in config.yaml: _______% (recommend: 0.5-1.0%)
  - [ ] Must cover: fees (0.1-0.6%) + slippage (0.1-0.5%) + profit margin (0.2%+)

- [ ] **Daily loss limits** configured
  - [ ] Maximum daily loss: $_______ (recommend: 2-5% of capital)
  - [ ] Circuit breaker tested (manually trigger and verify halt)

- [ ] **Emergency stop** tested
  - [ ] Know how to trigger: `Ctrl+C` or kill signal
  - [ ] Verified graceful shutdown closes positions
  - [ ] Emergency contact ready (exchange support, system admin)

---

## Phase 3: Operational Readiness

### Documentation Review

- [ ] **Read all documentation** thoroughly
  - [ ] README.md
  - [ ] ARCHITECTURE.md
  - [ ] DEPLOYMENT.md
  - [ ] SECURITY.md
  - [ ] RUNBOOK.md (troubleshooting procedures)
  - [ ] This PRODUCTION_READINESS.md (yes, all of it)

### Team & Support

- [ ] **Key personnel identified** (if team deployment)
  - [ ] System administrator: _________________
  - [ ] Trading operations: _________________
  - [ ] On-call rotation (24/7): _________________

- [ ] **Escalation procedures** documented
  - [ ] Who to call if system fails: _________________
  - [ ] Exchange support contacts saved: _________________
  - [ ] Cybersecurity incident response: _________________

- [ ] **Backup operators** trained
  - [ ] At least 2 people know how to start/stop the system
  - [ ] Emergency procedures documented and accessible

### Monitoring & Alerts

- [ ] **Alert channels configured and tested**
  - [ ] Telegram bot working (sent test message)
  - [ ] Email alerts working (sent test email)
  - [ ] PagerDuty/Slack (if applicable)

- [ ] **Alert rules configured for**:
  - [ ] System downtime (no heartbeat for 5 minutes)
  - [ ] Exchange API failures (3+ consecutive failures)
  - [ ] Abnormal spreads (negative spread executed)
  - [ ] Position size exceeded
  - [ ] Daily loss limit approaching (80% threshold)
  - [ ] Database connection errors
  - [ ] Redis connection errors

- [ ] **Dashboard monitoring** set up
  - [ ] Grafana dashboards accessible remotely (with authentication)
  - [ ] Key metrics monitored:
    - [ ] Opportunities per hour
    - [ ] Average spread
    - [ ] Execution success rate
    - [ ] API latency per exchange
    - [ ] System resource usage (CPU, memory, disk)

### Financial Setup

- [ ] **Exchange accounts funded** with minimal capital
  - [ ] Binance: $_______ (recommend: $500-2000 total across all exchanges)
  - [ ] Coinbase: $_______
  - [ ] Kraken: $_______
  - [ ] **Total capital at risk: $_______**

- [ ] **Balance distribution** appropriate for arbitrage
  - [ ] Each exchange has both USD and crypto for both sides of trade
  - [ ] Approximately equal value on each exchange (for simple arbitrage)
  - [ ] Example: If $1000 total, ~$333 on each of 3 exchanges

- [ ] **Tax record-keeping** prepared
  - [ ] Trade journal enabled (compliance module configured)
  - [ ] Understand your local tax obligations for crypto trading
  - [ ] CPA/accountant consulted (recommended)
  - [ ] Export scripts tested: `python scripts/export_trades.py`

### Legal & Compliance

- [ ] **Regulatory compliance** understood for your jurisdiction
  - [ ] Know your local crypto trading regulations
  - [ ] Aware of KYC/AML requirements
  - [ ] Understand tax reporting obligations
  - [ ] Consulted with lawyer if uncertain

- [ ] **Exchange Terms of Service** reviewed
  - [ ] Binance TOS read and accepted
  - [ ] Coinbase TOS read and accepted
  - [ ] Kraken TOS read and accepted
  - [ ] Confirmed automated trading is allowed

---

## Phase 4: Go-Live Checklist

### Pre-Launch (Day 0)

- [ ] **Final code review**
  - [ ] All tests pass: `make test`
  - [ ] No critical TODOs in code: `grep -r "TODO.*CRITICAL" src/`
  - [ ] Latest version deployed

- [ ] **Configuration review**
  - [ ] `mode: live` in config.yaml (NOT `mode: paper`)
  - [ ] All settings triple-checked (fees, limits, thresholds)
  - [ ] Exchange API keys valid (test in paper mode one more time)

- [ ] **Backup procedures tested**
  - [ ] Database backup created and verified
  - [ ] Configuration files backed up
  - [ ] .env file backed up (securely)
  - [ ] Know how to restore from backup

### Launch Day (Hour 0)

- [ ] **System start**
  - [ ] All infrastructure started: `make start`
  - [ ] Logs tailed: `make logs` (keep watching)
  - [ ] Dashboard open in browser
  - [ ] Telegram notifications coming through

- [ ] **Initial monitoring** (first 1 hour)
  - [ ] Verify exchange connections successful
  - [ ] Confirm orderbook data streaming
  - [ ] Watch for first opportunity detection
  - [ ] Monitor for any errors or warnings

### First Week of Live Trading

- [ ] **Daily checks** (every day for 7 days)
  - [ ] System uptime: _____ (target: 100%)
  - [ ] Trades executed: _____
  - [ ] Winning trades: _____
  - [ ] Losing trades: _____
  - [ ] Net profit/loss: $_____
  - [ ] Any anomalies: _____

- [ ] **End of week 1 review**
  - [ ] Actual vs. expected performance comparison
  - [ ] Any surprises or unexpected behavior
  - [ ] Decision: Continue, adjust, or stop?

### First Month of Live Trading

- [ ] **Weekly reviews** (weeks 2-4)
  - [ ] Week 2 net profit/loss: $_____
  - [ ] Week 3 net profit/loss: $_____
  - [ ] Week 4 net profit/loss: $_____
  - [ ] **Month 1 total profit/loss: $_____**

- [ ] **Performance metrics**
  - [ ] Sharpe ratio: _____ (target: > 1.0)
  - [ ] Win rate: _____% (target: > 60%)
  - [ ] Average trade size: $_____
  - [ ] Largest loss: $_____ (should be within risk limits)
  - [ ] Maximum drawdown: _____% (should be < daily loss limit)

- [ ] **Issue log review**
  - [ ] Critical issues encountered: _____
  - [ ] Resolution time: _____
  - [ ] Downtime total: _____ hours
  - [ ] Lessons learned: _____

---

## Phase 5: Continuous Operation

### Ongoing Maintenance

- [ ] **Daily tasks**
  - [ ] Check system status (5 minutes)
  - [ ] Review overnight trades
  - [ ] Check for alerts
  - [ ] Verify database disk space

- [ ] **Weekly tasks**
  - [ ] Review performance metrics
  - [ ] Check for software updates (CARBS, dependencies, exchanges)
  - [ ] Verify backups completed successfully
  - [ ] Review audit logs for anomalies

- [ ] **Monthly tasks**
  - [ ] Security audit (rotate API keys if recommended)
  - [ ] Update dependencies: `pip list --outdated`
  - [ ] Review and update risk parameters based on performance
  - [ ] Tax record reconciliation
  - [ ] System health report

### Scaling Considerations

**Only increase capital after:**

- [ ] 3+ months of profitable operation
- [ ] Consistent Sharpe ratio > 1.5
- [ ] Win rate > 70%
- [ ] No critical incidents in last 30 days
- [ ] All team members trained and confident

**Scaling guidelines:**

- Increase capital by MAX 50% per month
- Never deploy more than you can afford to lose
- Monitor for diminishing returns (market impact)
- Consider exchange position limits

---

## Decision Matrix: Should You Go Live?

### ✅ GREEN LIGHT (Proceed with caution)

- Paper trading > 4 weeks with consistent profitability
- All technical validations passed
- Security audit clean
- Performance benchmarks met
- Risk management configured conservatively
- Team trained and ready
- Starting with minimal capital ($100-500)
- Can monitor 24/7 for first week

### 🟡 YELLOW LIGHT (Delay and improve)

- Paper trading 2-4 weeks, marginal profitability
- Some technical issues but non-critical
- Security concerns identified but mitigatable
- Performance acceptable but not optimal
- Risk management adequate
- Limited monitoring capacity
- Starting with $500-1000

**Action**: Extend paper trading, address issues, recheck list

### 🔴 RED LIGHT (Do NOT go live)

- Paper trading < 2 weeks OR unprofitable
- Critical technical failures
- Security vulnerabilities unresolved
- Performance below thresholds
- Inadequate risk management
- No monitoring plan
- Planning to deploy significant capital (>$1000) immediately
- Cannot commit to daily monitoring

**Action**: Stop. More testing needed. Consult experts.

---

## Emergency Procedures

### If System Crashes

1. **Immediate**: Check exchange web UIs for open positions
2. **Within 5 min**: Manually close any open positions if market moved against you
3. **Within 15 min**: Check logs for cause: `tail -100 data/logs/app.log`
4. **Within 30 min**: Restart system if safe, or keep offline until issue resolved
5. **Within 24 hrs**: Conduct post-mortem, update this checklist

### If Losing Money Unexpectedly

1. **Immediate**: Execute emergency stop (Ctrl+C or `docker compose down`)
2. **Immediate**: Close all open positions manually via exchange UIs
3. **Within 1 hr**: Review last 10 trades in database
4. **Within 24 hrs**: Identify root cause (slippage? fees miscalculated? bug?)
5. **Do NOT restart** until issue fully understood and fixed

### If Exchange API Fails

1. **Immediate**: System should auto-skip that exchange (verify in logs)
2. **Within 5 min**: Check exchange status page (e.g., status.binance.com)
3. **If open position on failed exchange**: Monitor manually, close if needed
4. **If prolonged outage**: Consider disabling that exchange in config

---

## Resources

- **Documentation**: `/docs` folder in this repository
- **Logs**: `/data/logs/app.log` and `/data/audit/audit.log`
- **Grafana**: http://localhost:3000 (default)
- **Exchange Status Pages**:
  - Binance: https://www.binance.com/en/support/announcement
  - Coinbase: https://status.coinbase.com/
  - Kraken: https://status.kraken.com/

- **Support Channels**:
  - GitHub Issues: https://github.com/yourusername/carbs/issues
  - Documentation: This repository's /docs folder
  - Community: [Add if exists]

---

## Sign-Off

**By proceeding to live trading, I acknowledge:**

- ✅ I have completed ALL items on this checklist
- ✅ I understand the risks and accept them fully
- ✅ I am starting with minimal capital I can afford to lose
- ✅ I have a plan for daily monitoring and incident response
- ✅ I will NOT blame the software authors for any losses

**Signature:** _________________

**Date:** _________________

**Starting Capital:** $_________________

---

*This checklist is provided for guidance only. Completing this checklist does not guarantee profitability or eliminate risk. Trading cryptocurrency carries significant risk of loss.*
