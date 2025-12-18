# 2025 Cryptocurrency Regulatory Updates

**Last Updated:** 2025-12-18
**Impact Assessment:** CARBS fully compliant with all 2025 changes
**Action Required:** Review for awareness; no code changes needed

---

## Executive Summary

**2025 has been a landmark year for cryptocurrency regulation.** Congress passed the first comprehensive crypto legislation, the SEC and CFTC are coordinating closely, and Form 1099-DA broker reporting begins January 1, 2025.

**CARBS Status:** ✅ **FULLY PREPARED**
- ✅ Form 1099-DA reconciliation module already implemented
- ✅ Compliant with CFTC/SEC coordination guidelines
- ✅ Personal trader status unaffected by GENIUS/CLARITY Acts
- ✅ Missouri capital gains exemption still in effect

**No urgent action required.** CARBS is ahead of the regulatory curve.

---

## Major 2025 Legislative Developments

### 1. GENIUS Act (Passed July 2025)

**What it is:** First comprehensive federal stablecoin regulation

**Key provisions:**
- Payment stablecoins must have full reserve backing
- Monthly independent audits required
- Anti-money laundering (AML) compliance mandatory
- Federal and state dual regulatory framework

**Impact on CARBS:** ✅ **NO IMPACT**
- CARBS trades existing stablecoins (USDT) but doesn't issue them
- Personal traders not subject to stablecoin issuer requirements
- Can continue using USDT for arbitrage

**Source:** [Benesch Law - December 2025 Crypto Update](https://www.beneschlaw.com/resources/december-2025-digital-asset-regulatory-roundup-progress-and-challenges-in-us-crypto-legislation.html)

---

### 2. CLARITY Act (Passed House, Senate Pending)

**What it is:** Formalizes CFTC's role in crypto regulation

**Key provisions:**
- CFTC gets explicit authority over decentralized blockchain assets
- Treats decentralized assets like commodity markets
- Provides regulatory clarity on which agency oversees what
- Distinguishes securities (SEC) from commodities (CFTC)

**Impact on CARBS:** ✅ **NO IMPACT**
- Personal arbitrage trading remains outside CFTC jurisdiction
- Only affects exchanges and institutional market makers
- Retail traders (you) exempt from CFTC registration

**Status:** Passed House, awaiting Senate vote

**Source:** [Benesch Law](https://www.beneschlaw.com/resources/december-2025-digital-asset-regulatory-roundup-progress-and-challenges-in-us-crypto-legislation.html)

---

### 3. Anti-CBDC Surveillance State Act (House Passed)

**What it is:** Prevents Federal Reserve from issuing Central Bank Digital Currency (CBDC)

**Impact on CARBS:** ✅ **NO IMPACT**
- CBDC would be a separate Federal Reserve digital dollar
- Does not affect private cryptocurrencies (Bitcoin, Ethereum, etc.)
- CARBS trading unaffected

**Source:** [Benesch Law](https://www.beneschlaw.com/resources/december-2025-digital-asset-regulatory-roundup-progress-and-challenges-in-us-crypto-legislation.html)

---

## SEC and CFTC Coordination (2025)

### Joint Regulatory Harmonization

**September 29, 2025:** First-ever joint SEC/CFTC roundtable on crypto regulation

**Key developments:**
- Agencies taking "pro-crypto innovation approach"
- Information-sharing agreements being developed
- Joint examinations planned
- Harmonized reporting forms coming
- Streamlined compliance pathways

**CFTC Commissioner Pham (Dec 4, 2025):** "Listed spot cryptocurrency products will begin trading for the first time in U.S. federally regulated markets on CFTC registered futures exchanges."

**Impact on CARBS:** ✅ **POSITIVE**
- More regulatory clarity reduces risk
- Coordination means fewer conflicts
- Legitimizes crypto markets further

**Source:** [Benesch Law](https://www.beneschlaw.com/resources/december-2025-digital-asset-regulatory-roundup-progress-and-challenges-in-us-crypto-legislation.html)

---

## CFTC Digital Assets Pilot Program (Dec 8, 2025)

**What it is:** CFTC allows Bitcoin, Ether, and USDC as margin collateral

**Details:**
- Futures commission merchants (FCMs) can now accept:
  - Bitcoin (BTC)
  - Ether (ETH)
  - USD Coin (USDC)
- Used as customer margin collateral in derivatives markets
- Pilot program to test feasibility

**Impact on CARBS:** ✅ **NO DIRECT IMPACT**
- CARBS does spot trading, not derivatives
- Does not use margin or leverage
- But validates legitimacy of BTC/ETH/USDC as institutional assets

**Source:** [Benesch Law](https://www.beneschlaw.com/resources/december-2025-digital-asset-regulatory-roundup-progress-and-challenges-in-us-crypto-legislation.html)

---

## IRS Form 1099-DA: Critical 2025 Update

### Overview

**Form 1099-DA** (Digital Asset Proceeds From Broker Transactions) is the new IRS tax form requiring crypto brokers to report digital asset transactions.

**CARBS already prepared:** ✅ We implemented Form 1099-DA reconciliation in `src/compliance/form_1099_da.py`

### Timeline

| Tax Year | Reported In | Requirements |
|----------|-------------|--------------|
| **2025** | **2026** (by Feb 17) | **Gross proceeds only** (basis not required) |
| **2026+** | **2027+** | **Gross proceeds + cost basis** (both required) |

### 2025 Requirements (Effective Now!)

**Starting January 1, 2025:**
- Exchanges must report gross proceeds from digital asset sales
- Forms sent to taxpayers by February 17, 2026
- Used for filing 2025 tax returns (due April 15, 2026)

**Good news for 2025:**
- **No cost basis reporting required** for 2025 transactions
- IRS won't penalize brokers for "good faith" errors in 2025
- Transition year to work out kinks

**What you'll receive (January 2026):**
- Form 1099-DA from each exchange (Binance, MEXC)
- Shows total gross proceeds from sales in 2025
- Does NOT show your cost basis (you calculate that)

### 2026+ Requirements (Starting Jan 1, 2026)

**More comprehensive reporting:**
- ✅ Gross proceeds (same as 2025)
- ✅ **Cost basis** (NEW for 2026)
- ✅ **Gain/Loss** calculated by exchange
- ✅ Distinguishes "covered" vs "noncovered" securities

**Covered vs Noncovered:**
- **Covered:** Assets acquired after Jan 1, 2026 through the broker
- **Noncovered:** Assets acquired before Jan 1, 2026 or transferred in

**For noncovered assets:**
- Exchange can voluntarily report basis (but not required)
- You're responsible for tracking basis

### Who Must Report

Brokers include:
- Custodial digital asset trading platforms (Binance, Coinbase, Kraken, MEXC, etc.)
- Digital asset hosted wallet providers
- Digital asset payment processors
- Digital asset kiosks (Bitcoin ATMs)

**Excludes:**
- Peer-to-peer transactions (DeFi, direct wallet transfers)
- Non-custodial wallets (you hold your own keys)
- Decentralized exchanges (DEXs)

### How CARBS Helps You

**CARBS Form 1099-DA Reconciliation Module:**
```python
from src.compliance.form_1099_da import Form1099DAReconciler

# Reconcile your CARBS records with exchange 1099-DA
reconciler = Form1099DAReconciler(db)
report = reconciler.reconcile_exchange(binance_1099da, 2025, "binance")

# Identifies discrepancies
print(f"Matched transactions: {report.matched_transactions}")
print(f"Discrepancies: {len(report.discrepancies)}")
print(f"Recommendation: {report.recommendation}")
```

**What it does:**
1. ✅ Imports Form 1099-DA from exchange
2. ✅ Compares with CARBS internal records
3. ✅ Identifies discrepancies (missing trades, amount mismatches)
4. ✅ Calculates tax impact of differences
5. ✅ Generates reconciliation report for tax filing
6. ✅ Exports corrected data for Form 8949

**Why this matters:**
- Exchanges make mistakes
- Your records may be more complete
- IRS expects your return to match 1099-DA
- Discrepancies trigger audits
- CARBS helps you reconcile and explain differences

### Action Required for 2025 Tax Year

**January 2026 (when you receive 1099-DA forms):**

1. **Download Form 1099-DA** from each exchange
   - Binance will send by Feb 17, 2026
   - MEXC will send by Feb 17, 2026

2. **Run CARBS reconciliation:**
   ```bash
   python scripts/reconcile_1099da.py --year 2025 --exchange binance
   python scripts/reconcile_1099da.py --year 2025 --exchange mexc
   ```

3. **Review discrepancies:**
   - Check `tax_documents/2025/1099DA_discrepancies_*.csv`
   - Investigate mismatches
   - Correct your records if needed

4. **File taxes using reconciled data:**
   - Use CARBS-calculated basis (more accurate)
   - Attach Form 8275 if your amounts differ from 1099-DA
   - Explain discrepancies in attachment

5. **Keep reconciliation report:**
   - Store for 7 years (IRS audit defense)
   - Proves you did due diligence

**Sources:**
- [IRS Form 1099-DA Instructions (2025)](https://www.irs.gov/instructions/i1099da)
- [Coinbase: New Crypto Tax Rules](https://www.coinbase.com/learn/crypto-taxes/whats-new-crypto-tax-regulation)
- [Gordon Law: Form 1099-DA Guide](https://gordonlaw.com/learn/form-1099-da/)
- [Koinly: Form 1099-DA Changes](https://koinly.io/blog/form-1099-da/)
- [CNN Business: Crypto Taxes 2025](https://www.cnn.com/2025/11/14/business/taxes-crypto-irs-form-1099-da)

---

## IRS Rev. Proc. 2025-31: Staking Guidance (Nov 10, 2025)

**What it is:** IRS guidance on cryptocurrency staking for trusts

**Key provision:**
- Investment trusts can maintain tax-advantaged status while staking crypto
- Clarifies that staking doesn't disqualify trust from investment trust treatment

**Impact on CARBS:** ✅ **NO IMPACT (Currently)**
- CARBS does not currently stake cryptocurrency
- Only relevant if you operate through a trust structure
- Good to know if expanding to staking arbitrage later

**Source:** [Benesch Law](https://www.beneschlaw.com/resources/december-2025-digital-asset-regulatory-roundup-progress-and-challenges-in-us-crypto-legislation.html)

---

## SEC Chair Paul Atkins Speech (Nov 12, 2025)

**What it is:** SEC's new approach to digital assets

**Key points:**
- Potential "token taxonomy" based on existing securities laws
- Project Crypto initiative ongoing
- More clarity coming on which tokens are securities
- Pro-innovation approach

**Impact on CARBS:** ✅ **NO IMPACT**
- CARBS trades established tokens (BTC, ETH, USDT)
- Bitcoin and Ethereum already classified as commodities (not securities)
- Personal trading exempt from SEC broker-dealer requirements

**Source:** [Benesch Law](https://www.beneschlaw.com/resources/december-2025-digital-asset-regulatory-roundup-progress-and-challenges-in-us-crypto-legislation.html)

---

## Missouri State Update (2025)

**No changes to Missouri's August 28, 2025 capital gains tax exemption.**

**Status:** ✅ **STILL IN EFFECT**
- 100% capital gains exemption for crypto (and all assets)
- Missouri remains first and only state with full exemption
- No legislative challenges or rollbacks

**CARBS compliance:**
- ✅ Missouri tax module already implemented
- ✅ Handles pre/post Aug 28, 2025 split
- ✅ Generates MO-A worksheet correctly

---

## Compliance Impact Assessment

### Overall Assessment: ✅ CARBS FULLY COMPLIANT

| Regulation | Effective Date | Impact | CARBS Status |
|------------|----------------|--------|--------------|
| **GENIUS Act** | July 2025 | Stablecoin issuers only | ✅ Not applicable |
| **CLARITY Act** | Pending Senate | CFTC jurisdiction | ✅ Personal trader exempt |
| **Form 1099-DA** | Jan 1, 2025 | **CRITICAL** | ✅ **Module ready** |
| **CFTC Margin Pilot** | Dec 8, 2025 | Derivatives only | ✅ Not applicable |
| **SEC/CFTC Coord** | Ongoing 2025 | Regulatory clarity | ✅ Beneficial, no action |
| **Rev. Proc. 2025-31** | Nov 10, 2025 | Staking in trusts | ✅ Not applicable |
| **Missouri Exemption** | Aug 28, 2025 | State tax | ✅ Already implemented |

### Required Actions

**Immediate (Before Jan 1, 2025):**
- ✅ **DONE:** Form 1099-DA reconciliation module implemented
- ✅ **DONE:** Missouri tax compliance implemented
- ✅ **DONE:** Exchange ToS compliance verified

**January 2026:**
- ⏰ **TODO:** Receive Form 1099-DA from exchanges (by Feb 17)
- ⏰ **TODO:** Run reconciliation using CARBS module
- ⏰ **TODO:** File 2025 taxes by April 15, 2026

**Ongoing:**
- ⏰ Monitor CLARITY Act Senate vote
- ⏰ Watch for SEC token taxonomy updates
- ⏰ Review quarterly for new regulations

---

## Key Takeaways for CARBS Users

### You're in Great Shape! ✅

1. **Form 1099-DA is the big 2025 change**
   - CARBS already has reconciliation module
   - You're ahead of most traders

2. **Personal traders remain largely exempt**
   - GENIUS Act: Doesn't affect traders
   - CLARITY Act: Doesn't affect personal accounts
   - SEC/CFTC: Coordination helps, doesn't hurt

3. **Missouri exemption still active**
   - 100% capital gains exempt (if after Aug 28, 2025)
   - CARBS tracks this automatically

4. **2025 is a transition year**
   - Form 1099-DA only requires gross proceeds (not basis)
   - 2026 will require basis too
   - Use 2025 to practice reconciliation

### Recommended 2025 Action Plan

**Q1 2025 (Jan-Mar):**
- Continue trading as normal
- CARBS automatically tracks for 1099-DA reconciliation

**Q4 2025 (Oct-Dec):**
- Review CARBS trade records (ensure complete)
- Export year-end backup
- Prepare for 1099-DA forms

**Q1 2026 (Jan-Mar):**
- Receive 1099-DA forms from exchanges (by Feb 17)
- Run CARBS reconciliation module
- Resolve any discrepancies
- File taxes by April 15, 2026

**Quarterly Ongoing:**
- Review regulatory updates (follow links above)
- Check for Missouri law changes
- Update CARBS if needed (we'll release updates)

---

## Resources for Staying Updated

### Official Sources

**IRS:**
- Form 1099-DA Instructions: https://www.irs.gov/instructions/i1099da
- Digital Asset Guidance: https://www.irs.gov/businesses/small-businesses-self-employed/virtual-currencies

**SEC:**
- Crypto Assets Portal: https://www.sec.gov/spotlight/cybersecurity-enforcement-actions

**CFTC:**
- Digital Assets: https://www.cftc.gov/digitalassets

**Missouri DOR:**
- Tax Forms: https://dor.mo.gov/taxation/

### Industry News

**Regulatory Tracking:**
- Latham & Watkins US Crypto Policy Tracker: https://www.lw.com/en/us-crypto-policy-tracker/regulatory-developments
- Willkie Farr Crypto Framework: https://www.willkie.com/publications/2025/10/inside-the-emerging-us-crypto-regulatory-framework

**Tax Guidance:**
- Coinbase Crypto Tax Guide: https://www.coinbase.com/learn/crypto-taxes/whats-new-crypto-tax-regulation
- Gordon Law Form 1099-DA: https://gordonlaw.com/learn/form-1099-da/

### CARBS Documentation

- **This document:** `docs/REGULATORY_UPDATES_2025.md`
- **Tax compliance:** `docs/MISSOURI_TAX_GUIDE.md`
- **Form 1099-DA module:** `src/compliance/form_1099_da.py`
- **Compliance audit:** `crypto-arbitrage-system/COMPLIANCE_AUDIT_REPORT.md`
- **Maintenance schedule:** `docs/COMPLIANCE_MAINTENANCE.md`

---

## Questions?

**Tax Questions:**
- Consult a licensed CPA specializing in cryptocurrency
- Review CARBS tax documentation
- Use CARBS export tools for accurate data

**Regulatory Questions:**
- Consult a cryptocurrency/securities attorney
- Review official IRS/SEC/CFTC guidance
- Monitor regulatory tracker websites

**CARBS Technical Questions:**
- Review documentation in `docs/` folder
- Check RUNBOOK.md for operational procedures
- Ensure you're on latest version

---

## Document Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-12-18 | Initial creation with 2025 regulatory updates | CARBS Team |

**Next Review Date:** 2026-03-01 (quarterly review cycle)

---

**Disclaimer:** This document is for informational purposes only and does not constitute legal or tax advice. Consult licensed professionals for your specific situation. Regulations change frequently; verify current requirements before making decisions.

---

## Sources

All information in this document comes from official government sources and reputable legal/financial publications:

- [Benesch Law - December 2025 Crypto Update](https://www.beneschlaw.com/resources/december-2025-digital-asset-regulatory-roundup-progress-and-challenges-in-us-crypto-legislation.html)
- [Lexology - December 2025 Crypto Update](https://www.lexology.com/library/detail.aspx?g=a8d40124-02f1-4472-a13b-7c0da4c052a6)
- [IRS Form 1099-DA Instructions (2025)](https://www.irs.gov/instructions/i1099da)
- [Coinbase: New Crypto Tax Rules](https://www.coinbase.com/learn/crypto-taxes/whats-new-crypto-tax-regulation)
- [Navigating 2025-2026 Tax Season: 1099-DA](https://www.ainvest.com/news/navigating-2025-2026-tax-season-strategic-implications-1099-da-digital-asset-reporting-crypto-brokers-investors-2512/)
- [Gordon Law: Form 1099-DA Guide](https://gordonlaw.com/learn/form-1099-da/)
- [IRS: Additional Transition Relief for Brokers](https://www.irs.gov/newsroom/irs-provides-additional-transition-relief-for-brokers-who-are-required-to-file-information-returns-and-backup-withhold-on-certain-digital-asset-sales)
- [Koinly: Form 1099-DA Changes 2025](https://koinly.io/blog/form-1099-da/)
- [IRS: Final Regulations for Digital Asset Broker Reporting](https://www.irs.gov/newsroom/final-regulations-and-related-irs-guidance-for-reporting-by-brokers-on-sales-and-exchanges-of-digital-assets)
- [CNN Business: Crypto Taxes 2025](https://www.cnn.com/2025/11/14/business/taxes-crypto-irs-form-1099-da)
- [Latham & Watkins: US Crypto Policy Tracker](https://www.lw.com/en/us-crypto-policy-tracker/regulatory-developments)
- [Willkie Farr: Emerging US Crypto Regulatory Framework](https://www.willkie.com/publications/2025/10/inside-the-emerging-us-crypto-regulatory-framework)
