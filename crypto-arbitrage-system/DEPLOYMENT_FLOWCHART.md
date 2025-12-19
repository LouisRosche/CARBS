# 🗺️ CARBS Deployment Flowchart

**Visual guide to deploying CARBS from zero to production.**

---

## 📍 You Are Here

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  👤 NEW USER - Never used CARBS before                     │
│                                                             │
│  Goal: Deploy CARBS safely and compliantly                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                             │
                             │ Read START_HERE.md (5 min)
                             ▼
                    ┌─────────────────┐
                    │   UNDERSTAND    │
                    │   THE RISKS     │
                    └─────────────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
               YES  │                 │  NO
                    ▼                 ▼
            ┌───────────────┐   ┌──────────────┐
            │  I accept     │   │  STOP HERE   │
            │  all risks    │   │  Don't deploy│
            └───────────────┘   └──────────────┘
                    │
                    │ Read PRODUCTION_READINESS_REPORT.md (20 min)
                    ▼
```

---

## 🎯 Complete Deployment Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│  PHASE 1: PREPARATION (2-3 hours)                                    │
└──────────────────────────────────────────────────────────────────────┘
     │
     ├─► 1. Read Documentation
     │      ├─ START_HERE.md (5 min)
     │      ├─ PRODUCTION_READINESS_REPORT.md (20 min)
     │      ├─ docs/USER_RESPONSIBILITIES.md (10 min)
     │      └─ docs/REGULATORY_UPDATES_2025.md (30 min)
     │
     ├─► 2. Setup Exchange Accounts
     │      ├─ Create Binance.US account (30 min)
     │      ├─ Complete KYC verification (1-2 days wait)
     │      ├─ Enable 2FA (5 min)
     │      └─ Generate API keys (10 min)
     │         └─ Permissions: READ + TRADE only (NO WITHDRAWAL!)
     │
     ├─► 3. Verify System Requirements
     │      ├─ Python 3.11+ installed? ✓
     │      ├─ PostgreSQL 14+ installed? ✓
     │      ├─ Redis 6+ installed? ✓
     │      └─ 4GB+ RAM available? ✓
     │
     └─► 4. Clone Repository
            └─ git clone https://github.com/LouisRosche/CARBS.git

┌──────────────────────────────────────────────────────────────────────┐
│  PHASE 2: INSTALLATION (1-2 hours)                                   │
└──────────────────────────────────────────────────────────────────────┘
     │
     ├─► 5. Install Dependencies
     │      ├─ python3.11 -m venv venv
     │      ├─ source venv/bin/activate
     │      ├─ pip install -r requirements.txt
     │      └─ pip install -e .
     │
     ├─► 6. Configure Environment
     │      ├─ cp .env.example .env
     │      ├─ Edit .env:
     │      │   ├─ USER_JURISDICTION=US
     │      │   ├─ TRADING_MODE=paper  ◄── CRITICAL!
     │      │   ├─ BINANCE_API_KEY=xxx
     │      │   └─ BINANCE_API_SECRET=xxx
     │      └─ Edit config/config.yaml:
     │          ├─ mode: paper  ◄── CRITICAL!
     │          ├─ max_position_usd: 500
     │          ├─ max_daily_loss_usd: 100
     │          └─ exchanges: binance (enabled), kucoin (disabled)
     │
     ├─► 7. Setup Database
     │      ├─ docker-compose up -d postgres redis
     │      ├─ python scripts/setup_database.py
     │      └─ Verify: psql -U postgres -d carbs -c "\dt"
     │
     └─► 8. Run Tests
            ├─ pytest tests/test_compliance.py -v (15/15 pass?)
            └─ pytest tests/test_signals.py -v (21/21 pass?)

┌──────────────────────────────────────────────────────────────────────┐
│  PHASE 3: PAPER TRADING (2-4 weeks) ◄── MANDATORY!                  │
└──────────────────────────────────────────────────────────────────────┘
     │
     ├─► 9. Start Paper Trading
     │      ├─ python src/advanced_main.py
     │      ├─ Confirm mode: "PAPER TRADING MODE" in logs
     │      └─ Let run 24/7
     │
     ├─► 10. Monitor Daily (15-30 min/day)
     │      ├─ Check logs: tail -f data/logs/carbs.log
     │      ├─ Check dashboard: python src/cli/dashboard.py
     │      ├─ Review metrics: http://localhost:3000 (Grafana)
     │      └─ Track in spreadsheet:
     │          ├─ Opportunities found
     │          ├─ Average spread %
     │          ├─ False positives
     │          └─ Estimated profit
     │
     ├─► 11. Week 2 Checkpoint
     │      ├─ System stable? (no crashes)
     │      ├─ Opportunities detected? (>0 per day)
     │      ├─ Spreads profitable? (>0.2% after fees)
     │      └─ If NO to any → Troubleshoot or STOP
     │
     └─► 12. Week 4 Decision Point
            ├─ Average spread > 0.2%? ✓
            ├─ False positive rate < 50%? ✓
            ├─ Monthly profit > (capital * 5%)? ✓
            ├─ System stable for 4 weeks? ✓
            └─ If ALL ✓ → Proceed to Phase 4
                If ANY ✗ → STOP or extend paper trading

┌──────────────────────────────────────────────────────────────────────┐
│  PHASE 4: PRE-PRODUCTION VERIFICATION (2-4 hours)                    │
└──────────────────────────────────────────────────────────────────────┘
     │
     ├─► 13. Complete GO_LIVE_CHECKLIST.md
     │      ├─ Documentation Review (11 items)
     │      ├─ Exchange Account Setup (8 items)
     │      ├─ Environment Configuration (15 items)
     │      ├─ Database Setup (7 items)
     │      ├─ Paper Trading Results (12 items)
     │      ├─ Security Verification (10 items)
     │      ├─ Risk Management (8 items)
     │      ├─ Compliance Verification (9 items)
     │      ├─ Monitoring Setup (7 items)
     │      ├─ Pre-Live Verification (15 items)
     │      └─ Go-Live Execution (8 items)
     │         └─ Total: 110 checkboxes
     │
     ├─► 14. Final Configuration
     │      ├─ .env: TRADING_MODE=live
     │      ├─ config.yaml: mode: live
     │      ├─ Reduce limits for first week:
     │      │   ├─ max_position_usd: 100  ◄── Start TINY
     │      │   └─ max_daily_loss_usd: 20
     │      └─ Double-check API keys (NO WITHDRAWAL permission!)
     │
     └─► 15. Final Review
            ├─ All 110 checklist items complete?
            ├─ Backup database: pg_dump carbs > backup.sql
            ├─ Document baseline metrics
            └─ Prepare monitoring (set aside time for first 48 hours)

┌──────────────────────────────────────────────────────────────────────┐
│  PHASE 5: GO LIVE (First 48 hours are CRITICAL)                     │
└──────────────────────────────────────────────────────────────────────┘
     │
     ├─► 16. Start Live Trading
     │      ├─ python src/advanced_main.py
     │      ├─ Confirm: "LIVE TRADING MODE" in logs ◄── VERIFY!
     │      ├─ Watch first trade execute
     │      └─ Verify funds moved correctly
     │
     ├─► 17. First 24 Hours (Monitor CONSTANTLY)
     │      ├─ Check logs every 15-30 minutes
     │      ├─ Verify every trade in exchange UI
     │      ├─ Monitor profit/loss in real-time
     │      ├─ Check for any errors immediately
     │      └─ Be ready to shut down if issues arise
     │
     ├─► 18. First Week (Monitor CLOSELY)
     │      ├─ Daily PnL review
     │      ├─ Compare to paper trading results
     │      ├─ Identify any unexpected behavior
     │      ├─ Gradual limit increases (if successful):
     │      │   └─ Day 3: max_position_usd: 200
     │      │   └─ Day 5: max_position_usd: 500
     │      └─ STOP if:
     │          ├─ Net loss > $50
     │          ├─ More than 2 failed trades
     │          ├─ Any unexplained errors
     │          └─ Results much worse than paper trading
     │
     └─► 19. First Month (Monitor REGULARLY)
            ├─ Weekly performance review
            ├─ Monthly compliance exports
            ├─ Gradual capital scaling (if profitable)
            └─ Adjust strategy based on results

┌──────────────────────────────────────────────────────────────────────┐
│  PHASE 6: ONGOING OPERATIONS                                         │
└──────────────────────────────────────────────────────────────────────┘
     │
     ├─► 20. Daily Operations
     │      ├─ Check dashboard once per day
     │      ├─ Review logs for errors
     │      └─ Track profitability
     │
     ├─► 21. Weekly Tasks
     │      ├─ Backup database
     │      ├─ Review performance metrics
     │      ├─ Check exchange account balances
     │      └─ Update trading journal
     │
     ├─► 22. Monthly Tasks
     │      ├─ Export compliance reports
     │      ├─ Generate tax exports (if needed)
     │      ├─ Review and adjust risk limits
     │      └─ Update software if new version available
     │
     ├─► 23. Quarterly Tasks
     │      ├─ Full system audit
     │      ├─ Estimated tax calculation
     │      ├─ Review regulatory changes
     │      └─ Assess profitability vs. alternatives
     │
     └─► 24. Annual Tasks
            ├─ File taxes (Form 8949, Schedule D, MO-A)
            ├─ Archive audit logs (7-year retention)
            ├─ Review and renew exchange accounts
            └─ Full compliance review

```

---

## ⏱️ Timeline Summary

| Phase | Duration | Can Skip? | Critical? |
|-------|----------|-----------|-----------|
| 1. Preparation | 2-3 hours | ❌ NO | ✅ YES |
| 2. Installation | 1-2 hours | ❌ NO | ✅ YES |
| 3. Paper Trading | 2-4 weeks | ❌ NO | ✅ YES |
| 4. Pre-Production | 2-4 hours | ❌ NO | ✅ YES |
| 5. Go Live | 48 hours | ❌ NO | ✅ YES |
| 6. Operations | Ongoing | ❌ NO | ✅ YES |

**Total Time to Live Trading:** Minimum 3-5 weeks

**Can't be rushed:** Paper trading (2-4 weeks) + KYC verification (1-2 days)

---

## 🚨 Critical Decision Points

```
┌─────────────────────────────────────────────────────────┐
│  STOP POINT #1: After Reading Documentation            │
│  Question: Can I afford to lose all my capital?        │
│  └─ NO → STOP, don't proceed                           │
│  └─ YES → Continue                                      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  STOP POINT #2: Week 2 of Paper Trading                │
│  Question: Is the system stable and finding opps?      │
│  └─ NO → Troubleshoot or STOP                          │
│  └─ YES → Continue paper trading                        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  STOP POINT #3: Week 4 of Paper Trading                │
│  Question: Is it profitable? (spread >0.2% after fees) │
│  └─ NO → STOP, not profitable enough                   │
│  └─ YES → Proceed to go-live verification              │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  STOP POINT #4: End of First Week Live                 │
│  Question: Results matching paper trading?             │
│  └─ NO → STOP, investigate issues                      │
│  └─ YES → Continue with gradual scaling                │
└─────────────────────────────────────────────────────────┘
```

---

## 📊 Success Metrics by Phase

### Phase 3: Paper Trading Success Criteria

| Metric | Target | Action if Below Target |
|--------|--------|------------------------|
| System Uptime | >99% | Fix stability issues |
| Opportunities/Day | >10 | Check exchange connectivity |
| Average Spread (before fees) | >0.5% | May not be profitable |
| Average Spread (after fees) | >0.2% | **STOP - Not profitable** |
| False Positive Rate | <50% | Reduce latency or improve data quality |
| Monthly ROI (estimated) | >5% | Consider if worth the risk |

### Phase 5: First Week Live Success Criteria

| Metric | Target | Action if Below Target |
|--------|--------|------------------------|
| Actual spread vs paper | >80% match | Investigate slippage/fees |
| Successful trade rate | >90% | Check execution logic |
| Daily PnL | Positive | **STOP if negative for 3+ days** |
| Error rate | <1% | Fix bugs immediately |
| Unexpected behavior | 0 incidents | **STOP and investigate** |

---

## 🔄 Quick Reference: Where Am I?

**Use this to find your current position:**

```
□ Haven't started → Read START_HERE.md → Phase 1
□ Read docs, no exchange account → Setup exchanges → Phase 1
□ Have exchange account, not installed → Install software → Phase 2
□ Software installed, not configured → Configure environment → Phase 2
□ Configured, not paper trading → Start paper trading → Phase 3
□ Paper trading < 2 weeks → Continue paper trading → Phase 3
□ Paper trading 2-4 weeks → Evaluate results → Phase 3
□ Paper trading successful → Complete checklist → Phase 4
□ Checklist complete → Go live (CAREFULLY!) → Phase 5
□ Live for < 1 week → Monitor CONSTANTLY → Phase 5
□ Live for 1+ weeks → Establish operations routine → Phase 6
```

---

## 📞 Get Help

**Stuck on a phase?** Reference these docs:

- **Phase 1-2:** [docs/PRODUCTION_DEPLOYMENT_GUIDE.md](docs/PRODUCTION_DEPLOYMENT_GUIDE.md)
- **Phase 3:** [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) (checklist)
- **Phase 4:** [GO_LIVE_CHECKLIST.md](GO_LIVE_CHECKLIST.md)
- **Phase 5-6:** [docs/RUNBOOK.md](docs/RUNBOOK.md)
- **General:** [DOCUMENTATION_HUB.md](DOCUMENTATION_HUB.md)

---

## ⚡ Fast Track (NOT RECOMMENDED)

**Absolute minimum to go live (RISKY):**

1. Read START_HERE.md + USER_RESPONSIBILITIES.md (30 min)
2. Setup exchange account + KYC (2-3 hours + 1-2 days wait)
3. Install software + configure (2 hours)
4. Paper trade for 2 weeks minimum (can't be rushed)
5. Complete GO_LIVE_CHECKLIST.md (2 hours)
6. Go live with $100 max (1 hour)

**Total: ~3 weeks minimum**

**Why NOT recommended:**
- Skips important documentation
- Minimal paper trading (4 weeks better)
- Higher risk of mistakes
- May miss critical compliance requirements

**Better approach:** Follow full timeline (4-5 weeks)

---

**Ready to start?** → Go to [START_HERE.md](START_HERE.md)

**Want detailed steps?** → Go to [docs/PRODUCTION_DEPLOYMENT_GUIDE.md](docs/PRODUCTION_DEPLOYMENT_GUIDE.md)

**Need all docs organized?** → Go to [DOCUMENTATION_HUB.md](DOCUMENTATION_HUB.md)

---

*Last Updated: 2025-12-19 | This flowchart covers the complete deployment lifecycle from zero to production.*
