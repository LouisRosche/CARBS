# Compliance Maintenance Schedule

**Document Purpose:** Annual and ongoing compliance maintenance procedures for CARBS cryptocurrency arbitrage trading system.

**Owner:** System operator (personal trader)
**Last Updated:** 2025-12-18
**Next Review:** 2026-01-15

---

## Overview

Maintaining compliance is an ongoing process, not a one-time task. This document outlines the regular maintenance activities required to ensure CARBS remains compliant with:

- **Federal IRS** tax requirements
- **Missouri state** tax requirements
- **Exchange** Terms of Service
- **Regulatory** changes in cryptocurrency law
- **Data retention** and security obligations

---

## Annual Tasks (January Each Year)

### 1. Tax Preparation (January 1-31)

**Priority:** CRITICAL
**Deadline:** January 31 (to allow time for filing before April 15)

#### Tasks:

- [ ] **Export all trade data for prior tax year**
  ```bash
  python scripts/export_missouri_tax.py --year 2025 --name "Your Name"
  ```

- [ ] **Reconcile Form 1099-DA (starting 2026)**
  - Download 1099-DA forms from all exchanges (they send by Jan 31)
  - Run reconciliation module for each exchange:
    ```python
    from src.compliance.form_1099_da import Form1099DAReconciler
    # reconciler = Form1099DAReconciler(db)
    # report = reconciler.reconcile_exchange(form, 2025, "binance")
    ```
  - Review discrepancies and resolve
  - Keep reconciliation report with tax records

- [ ] **Generate Form 8949 and Schedule D data**
  - CARBS automatically generates these
  - Review for accuracy
  - Provide to tax preparer or import to tax software

- [ ] **Calculate Missouri tax (if applicable)**
  - For trades before Aug 28, 2025: MO-A worksheet generated automatically
  - For trades after Aug 28, 2025: 100% capital gains exemption

- [ ] **Verify cost basis accuracy**
  - Review cost basis method (FIFO, HIFO, etc.)
  - Ensure consistent with prior years
  - Check for any missing acquisitions

- [ ] **Document wash sale adjustments (if any)**
  - CARBS tracks same-asset trades
  - Review for wash sale rules (30-day rule)
  - Adjust basis if needed

- [ ] **Backup all tax-related data**
  - Export to external drive
  - Store for 7 years (IRS requirement)
  - Include: trades CSV, Form 8949, audit logs, 1099-DA reconciliation

#### Deliverables:
- ✅ trades_YYYY.csv
- ✅ form_8949_YYYY.csv
- ✅ Missouri_Tax_Summary_YYYY.txt (if MO resident)
- ✅ MO-A_Worksheet_YYYY.txt (if trades before Aug 28, 2025)
- ✅ 1099-DA reconciliation reports (starting 2026)
- ✅ Cost basis summary

---

### 2. Exchange ToS Review (January 15)

**Priority:** HIGH
**Frequency:** Quarterly (Jan, Apr, Jul, Oct)

#### Tasks:

- [ ] **Review Binance/Binance.US Terms of Service**
  - Visit: https://www.binance.com/en/terms
  - Check "Last Updated" date
  - Note any material changes
  - Update EXCHANGE_COMPLIANCE.md if needed

- [ ] **Review MEXC Terms of Service**
  - Visit: https://www.mexc.com/user-agreement
  - Check for geographic restrictions
  - Note policy changes
  - Update documentation

- [ ] **Review KuCoin Terms of Service**
  - Visit: https://www.kucoin.com/agreement
  - **Monitor regulatory status** (ongoing enforcement)
  - Check if US restrictions changed
  - Consider disabling if regulatory risk too high

- [ ] **Check for new exchange compliance requirements**
  - API usage policy changes
  - Rate limit adjustments
  - KYC verification updates
  - Geographic restrictions

- [ ] **Verify CARBS compliance with current ToS**
  - Review trading patterns
  - Ensure no prohibited activities
  - Check rate limiter configuration matches new limits

#### Deliverables:
- ✅ Updated EXCHANGE_COMPLIANCE.md (if changes found)
- ✅ Log of ToS review in compliance audit log

---

### 3. Regulatory Update Review (January 15)

**Priority:** HIGH
**Frequency:** Annual (January) + as needed when major news breaks

#### Tasks:

- [ ] **Check IRS cryptocurrency guidance**
  - Visit: https://www.irs.gov/businesses/small-businesses-self-employed/virtual-currencies
  - Review any new revenue procedures or notices
  - Check for Form 8949 or 1099-DA changes
  - Note deadline changes

- [ ] **Missouri tax law updates**
  - Visit: https://dor.mo.gov/taxation/
  - Check if capital gains exemption still in effect
  - Review any new crypto-specific guidance
  - Update missouri_tax.py if needed

- [ ] **SEC cryptocurrency regulation**
  - Visit: https://www.sec.gov/spotlight/cybersecurity-enforcement-actions
  - Check for new enforcement actions against exchanges
  - Review any new securities classification (Bitcoin, Ethereum status)
  - Assess impact on CARBS

- [ ] **CFTC crypto derivatives regulation**
  - Visit: https://www.cftc.gov/digitalassets
  - Check for changes affecting spot trading
  - Review any new retail trader restrictions
  - Update if necessary

- [ ] **FinCEN AML updates**
  - Visit: https://www.fincen.gov/
  - Check for changes to MSB/money transmitter definitions
  - Verify personal trader exemption still valid
  - Review travel rule updates

- [ ] **State-level crypto regulation (Missouri)**
  - Check Missouri Legislature: https://www.senate.mo.gov/
  - Search for new cryptocurrency bills
  - Review any new licensing requirements
  - Update compliance if needed

#### Deliverables:
- ✅ Regulatory changes log
- ✅ Updated COMPLIANCE_AUDIT_REPORT.md (if material changes)
- ✅ Action items if code changes needed

---

### 4. Data Retention and Archival (January 31)

**Priority:** CRITICAL
**Frequency:** Annual

#### Tasks:

- [ ] **Verify audit log retention (7 years)**
  - Check src/security/audit.py retention setting (should be 2555 days)
  - Verify old logs are NOT being deleted prematurely
  - Review audit log integrity: `audit_logger.verify_integrity()`

- [ ] **Backup PostgreSQL database**
  ```bash
  pg_dump carbs_db > backups/carbs_db_YYYY_MM_DD.sql
  gzip backups/carbs_db_YYYY_MM_DD.sql
  ```

- [ ] **Archive trade history (permanent)**
  - Export complete trade history: `python scripts/export_all_trades.py`
  - Store on external drive (not cloud)
  - Keep for 7 years minimum (IRS requirement)
  - Include: trades, cost basis, audit logs, tax forms

- [ ] **Verify backup integrity**
  - Test restore of database backup
  - Verify CSV exports are readable
  - Check that audit logs are intact and hash chains valid

- [ ] **Secure storage of backups**
  - Encrypt sensitive data (API keys, personal info)
  - Store in fireproof safe or safety deposit box
  - Keep multiple copies in different physical locations
  - Do NOT rely solely on cloud storage (subpoena risk)

#### Deliverables:
- ✅ Database backup (encrypted)
- ✅ Complete trade history CSV
- ✅ Audit logs (7 years)
- ✅ Tax forms and reconciliation reports
- ✅ Backup integrity test passed

---

## Quarterly Tasks (Jan, Apr, Jul, Oct)

### 1. Exchange Account Health Check (15th of each quarter)

**Priority:** MEDIUM
**Frequency:** Quarterly

#### Tasks:

- [ ] **Verify KYC status on all exchanges**
  - Log into each exchange
  - Check verification status
  - Renew if expiring soon
  - Update contact information if changed

- [ ] **Review API key security**
  - Check API key permissions (trading only, no withdrawals)
  - Verify IP whitelist is current
  - Rotate API keys (recommended every 90 days)
  - Test CARBS connection after rotation

- [ ] **Check account standing**
  - Review for any warnings or restrictions
  - Check email for compliance notifications
  - Verify trading permissions are active
  - Ensure no pending actions required

- [ ] **Download transaction history**
  - Export from each exchange (quarterly backup)
  - Compare with CARBS records
  - Identify any missing transactions
  - Import missing trades to CARBS if found

#### Deliverables:
- ✅ API keys rotated (if due)
- ✅ Exchange transaction history exported
- ✅ Account status: GOOD / ISSUE FOUND

---

### 2. CARBS System Health (15th of each quarter)

**Priority:** MEDIUM
**Frequency:** Quarterly

#### Tasks:

- [ ] **Review system logs for compliance issues**
  ```bash
  grep "AUDIT" logs/carbs.log | grep "ERROR\|WARNING" | tail -100
  ```

- [ ] **Verify all trades are being recorded**
  - Check database record count vs. expected
  - Review audit log completeness
  - Verify no dropped transactions

- [ ] **Test export functionality**
  - Run Missouri tax export: `python scripts/export_missouri_tax.py --year 2025 --name "Test"`
  - Verify CSV format is correct
  - Check Form 8949 generation
  - Ensure no errors

- [ ] **Update CARBS dependencies (security patches)**
  ```bash
  pip list --outdated
  # Update only security patches, not major versions
  pip install --upgrade <package>
  ```

- [ ] **Run compliance test suite (if implemented)**
  ```bash
  pytest tests/test_compliance.py -v
  ```

#### Deliverables:
- ✅ System health report
- ✅ No compliance errors in logs
- ✅ Export tests passed
- ✅ Dependencies updated

---

## Monthly Tasks (1st of each month)

### 1. Routine Monitoring (1st of each month)

**Priority:** LOW
**Frequency:** Monthly

#### Tasks:

- [ ] **Check for exchange announcements**
  - Subscribe to exchange newsletters
  - Review announcement pages:
    - Binance: https://www.binance.com/en/support/announcement
    - MEXC: https://www.mexc.com/support/sections/360000291333
    - KuCoin: https://www.kucoin.com/news
  - Note any API changes, maintenance, or policy updates

- [ ] **Review CARBS trading logs**
  - Check for any errors or warnings
  - Review failed trades
  - Verify rate limiters are working correctly

- [ ] **Database maintenance**
  ```bash
  # Vacuum database to reclaim space
  psql carbs_db -c "VACUUM ANALYZE;"
  ```

#### Deliverables:
- ✅ Exchange announcements reviewed
- ✅ No critical errors found
- ✅ Database optimized

---

## Event-Driven Tasks (As Needed)

### 1. When Exchange Changes ToS

**Trigger:** Exchange updates Terms of Service
**Priority:** HIGH

#### Immediate Actions:

1. **Read the updated ToS carefully**
   - Focus on sections about API usage, automated trading, arbitrage
   - Look for new prohibited activities
   - Check geographic restrictions

2. **Assess CARBS compatibility**
   - Does CARBS violate any new terms?
   - Are there new rate limits?
   - Are there new KYC requirements?

3. **Update documentation**
   - Update EXCHANGE_COMPLIANCE.md with changes
   - Document the change date and nature
   - Add any new compliance checks

4. **Modify CARBS if needed**
   - Update rate limiters
   - Adjust trading strategies
   - Add new compliance checks

5. **Test changes**
   - Verify CARBS still works correctly
   - Check logs for compliance with new ToS
   - Monitor for any issues

---

### 2. When Regulatory Change Occurs

**Trigger:** New law, IRS guidance, or regulatory enforcement
**Priority:** CRITICAL

#### Immediate Actions:

1. **Understand the change**
   - Read the full text of new regulation
   - Consult legal resources or attorney if significant
   - Identify effective date and compliance deadline

2. **Assess impact on CARBS**
   - Does it affect trading activities?
   - Are there new reporting requirements?
   - Are there new record-keeping obligations?

3. **Plan implementation**
   - List required code changes
   - Identify documentation updates
   - Determine if external help needed (CPA, lawyer)

4. **Implement changes**
   - Update code (cost basis, reporting, exports)
   - Update documentation
   - Test thoroughly

5. **Document compliance**
   - Update COMPLIANCE_AUDIT_REPORT.md
   - Add to COMPLIANCE_MAINTENANCE.md (this document)
   - Log in audit system

---

### 3. When Form 1099-DA Is Received (2026+)

**Trigger:** Exchange sends Form 1099-DA (by January 31)
**Priority:** CRITICAL

#### Immediate Actions:

1. **Import Form 1099-DA data**
   - Download from exchange
   - Parse into CARBS format
   - Create Form1099DA object

2. **Run reconciliation**
   ```python
   from src.compliance.form_1099_da import Form1099DAReconciler
   reconciler = Form1099DAReconciler(db)
   report = reconciler.reconcile_exchange(form_1099da, 2025, "binance")
   ```

3. **Review discrepancies**
   - Check report.discrepancies list
   - Investigate each mismatch
   - Determine correct values

4. **Resolve issues**
   - If exchange is wrong: Contact exchange support, request corrected 1099-DA
   - If CARBS is wrong: Update records, recalculate cost basis
   - If both wrong: Investigate source of truth

5. **Export reconciliation report**
   ```python
   reconciler.export_reconciliation_report(report, Path("tax_documents/2025"))
   ```

6. **File taxes with correct data**
   - Use reconciled values for Form 8949
   - Attach Form 8275 if using different values than 1099-DA
   - Keep reconciliation report for audit defense

---

### 4. When Exchange Gets Regulatory Action

**Trigger:** Exchange faces SEC, CFTC, or DOJ enforcement
**Priority:** CRITICAL

#### Immediate Actions:

1. **Stop trading on that exchange**
   - Disable exchange in CARBS config
   - Do not place new orders

2. **Preserve records**
   - Export complete trade history immediately
   - Download all account statements
   - Take screenshots of account balances
   - Backup everything locally

3. **Assess risk**
   - Can you withdraw funds?
   - Are accounts at risk of freezing?
   - Are you personally liable for anything?

4. **Withdraw funds if possible**
   - Transfer to wallet or another exchange
   - Keep records of all withdrawals

5. **Consult professionals**
   - Tax attorney (if large amounts involved)
   - CPA (for tax implications)
   - Consider your options

6. **Update CARBS**
   - Disable exchange permanently if shut down
   - Update EXCHANGE_COMPLIANCE.md with status
   - Document in COMPLIANCE_AUDIT_REPORT.md

---

## Compliance Calendar

### Summary View

| Task | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
|------|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
| Tax Prep | ✅ | | | | | | | | | | | |
| File Taxes | | | | ✅ | | | | | | | | |
| ToS Review | ✅ | | | ✅ | | | ✅ | | | ✅ | | |
| Reg Review | ✅ | | | | | | | | | | | |
| Data Backup | ✅ | | | | | | | | | | | |
| API Rotation | ✅ | | | ✅ | | | ✅ | | | ✅ | | |
| System Health | ✅ | | | ✅ | | | ✅ | | | ✅ | | |
| Monthly Check | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Checklists for Busy People

### January Master Checklist

```
JANUARY COMPLIANCE CHECKLIST (The busy month!)

Week 1 (Jan 1-7):
□ Export all trade data for prior tax year
□ Download Form 1099-DA from all exchanges (available by Jan 31)
□ Run Form 1099-DA reconciliation (starting 2026)
□ Generate Form 8949 and Missouri forms

Week 2 (Jan 8-14):
□ Review and resolve any 1099-DA discrepancies
□ Calculate total capital gains/losses
□ Prepare tax package for CPA (if using one)

Week 3 (Jan 15-21):
□ Exchange ToS review (all 3 exchanges)
□ Regulatory update research (IRS, SEC, CFTC, FinCEN, Missouri)
□ Update EXCHANGE_COMPLIANCE.md if needed

Week 4 (Jan 22-31):
□ Database backup and archival
□ Verify 7-year data retention
□ Test backup integrity
□ Rotate API keys (quarterly)
□ System health check

By Jan 31:
✅ Tax documents ready
✅ Compliance reviews complete
✅ Backups secure
✅ Ready for April 15 tax filing
```

---

### Quarterly Checklist (Apr, Jul, Oct)

```
QUARTERLY COMPLIANCE CHECKLIST (15th of the month)

Exchange Health:
□ Verify KYC status on all exchanges
□ Rotate API keys (every 90 days)
□ Check account standing (no warnings/restrictions)
□ Download transaction history from exchanges

System Health:
□ Review CARBS logs for errors
□ Test export functionality
□ Update dependencies (security patches only)
□ Run compliance test suite

Documentation:
□ Review exchange ToS for changes
□ Update EXCHANGE_COMPLIANCE.md if needed
□ Check for regulatory updates

Time Required: ~2 hours
```

---

### Monthly Checklist (1st of month)

```
MONTHLY COMPLIANCE CHECKLIST (Quick check)

□ Check exchange announcements for updates
□ Review CARBS logs for errors or warnings
□ Run database maintenance (VACUUM ANALYZE)
□ Verify no failed trades or missing data

Time Required: ~15 minutes
```

---

## Automation Opportunities

### Consider Automating:

1. **Monthly database backup**
   ```bash
   # Add to crontab:
   0 2 1 * * /path/to/backup_script.sh
   ```

2. **Log monitoring**
   - Set up alerts for ERROR/CRITICAL in audit logs
   - Email notification for compliance issues

3. **Exchange announcement monitoring**
   - RSS feeds or web scraping
   - Alert when ToS "Last Updated" changes

4. **Regulatory news monitoring**
   - Subscribe to IRS, SEC, CFTC newsletters
   - Google Alerts for "cryptocurrency regulation"

### DO NOT Automate:

- Tax filing (requires human review)
- ToS review (requires understanding changes)
- Regulatory compliance decisions (requires judgment)
- Form 1099-DA reconciliation (requires investigation)

---

## Recordkeeping Requirements

### What to Keep Forever:

- All trade records (indefinite retention recommended)
- All tax returns and supporting documents (7 years minimum, forever recommended)
- Cost basis calculations for all assets
- Audit logs (7 years IRS requirement)

### What to Keep for 7 Years:

- Form 8949 and Schedule D
- Form 1099-DA and reconciliation reports
- Missouri tax forms (MO-A worksheets)
- Audit logs
- Bank statements showing exchange deposits/withdrawals

### What to Keep for 3 Years:

- Exchange transaction history exports
- System logs (non-audit)
- Performance logs

### What You Can Delete:

- Temporary files
- Debug logs (after reviewing)
- Old software versions (after testing new version)

---

## Red Flags to Monitor

### Indicators of Compliance Issues:

⚠️ **Tax Red Flags:**
- Form 1099-DA doesn't match your records (>$100 difference)
- Missing trades from your records
- Cost basis errors or inconsistencies
- Wash sales not properly adjusted

⚠️ **Exchange Red Flags:**
- Account verification failing or expiring
- Warnings or restrictions on your account
- API keys getting rate limited excessively
- Unable to download complete transaction history

⚠️ **Regulatory Red Flags:**
- Exchange you use faces enforcement action
- New regulations affect your trading activities
- Changes to crypto tax law
- Missouri changes capital gains exemption

⚠️ **System Red Flags:**
- CARBS audit logs show integrity failures
- Trades not being recorded in database
- Export functions failing
- Database corruption or data loss

### What to Do If You See Red Flags:

1. **STOP TRADING** until resolved
2. **Document** the issue immediately
3. **Investigate** root cause
4. **Fix** the issue
5. **Test** thoroughly
6. **Resume** only when confirmed fixed
7. **Consult professionals** if significant

---

## Resources

### Tax Professionals

- **Find a CPA specializing in cryptocurrency:**
  - https://www.aicpa.org/
  - Search for "cryptocurrency tax CPA Missouri"

- **IRS Help:**
  - Taxpayer Advocate Service: 1-877-777-4778
  - IRS Crypto Hotline: Check IRS website for current number

### Legal Resources

- **Find a cryptocurrency attorney:**
  - Your state bar association
  - Search for "blockchain attorney Missouri"

- **SEC/CFTC Issues:**
  - Consult a securities attorney
  - DO NOT ignore enforcement actions

### Compliance Tools

- **Tax Software with Crypto Support:**
  - TurboTax (Premier or Self-Employed)
  - TaxAct
  - FreeTaxUSA
  - H&R Block

- **Crypto Tax Specialists:**
  - CoinTracker (double-check before trusting)
  - TokenTax
  - ZenLedger

**Note:** CARBS exports work with most tax software. You may not need specialized crypto tax software since CARBS already calculates cost basis and generates Form 8949.

---

## Emergency Contacts

### In Case of Compliance Emergency

**Tax Issue:**
1. Contact your CPA immediately
2. If no CPA: IRS Taxpayer Advocate Service (1-877-777-4778)
3. DO NOT ignore IRS notices

**Exchange Account Issue:**
1. Contact exchange support
2. Document all communications
3. Consider consulting attorney if funds at risk

**Regulatory Action:**
1. Consult attorney IMMEDIATELY
2. Preserve all records
3. Do not speak to regulators without counsel

**Data Loss:**
1. Restore from most recent backup
2. Contact database administrator (if you have one)
3. Export any recoverable data from exchanges

---

## Document Revision History

| Version | Date       | Changes                          | Author     |
|---------|------------|----------------------------------|------------|
| 1.0     | 2025-12-18 | Initial creation                 | CARBS Team |

**Next scheduled review:** 2026-01-15

---

## Certification

By following this compliance maintenance schedule, you demonstrate good faith effort to comply with all applicable regulations. Keep this document updated as regulations change.

**Remember:** Compliance is ongoing, not one-time. Set calendar reminders for all deadlines above.

**Questions?** Consult a licensed CPA and attorney for your specific situation.
