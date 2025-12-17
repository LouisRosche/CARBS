# Missouri Cryptocurrency Tax Guide

**For Missouri Residents Trading Cryptocurrency**

**Last Updated:** 2025-12-17

---

## 🎉 HISTORIC NEWS: Missouri Eliminates Capital Gains Tax

**As of August 28, 2025, Missouri became the FIRST U.S. state to eliminate capital gains tax on stocks, cryptocurrency, and real estate.**

This is a major development for cryptocurrency traders in Missouri!

### Sources
- [Fortune: Missouri becomes first U.S. state to exempt crypto sale profits from income taxes](https://fortune.com/2025/05/08/missouri-first-us-state-exempt-stock-crypto-sale-profits-income-taxes/)
- [KCUR: Missouri is first state to repeal capital gains tax](https://www.kcur.org/politics-elections-and-government/2025-08-28/missouri-capital-gains-tax-repeal-income-stocks-real-estate-crypto)
- [Missouri Crypto Tax Guide - Law Office of Chad G. Mann](https://chadgmann.com/2024/10/15/navigating-the-tax-labyrinth-understanding-cryptocurrency-taxes-in-missouri-and-federal-law/)

---

## Summary

| Tax Type | Status | Details |
|----------|--------|---------|
| **Missouri State Tax** | **EXEMPT** (as of Aug 28, 2025) | 100% capital gains exemption |
| **Federal Tax** | **STILL APPLIES** | Must file Form 8949, Schedule D |
| **Short-term gains (<1 year)** | **EXEMPT in MO** | Federally taxed as ordinary income |
| **Long-term gains (>1 year)** | **EXEMPT in MO** | Federally taxed at capital gains rates |

---

## What This Means for You

### ✅ Good News

1. **No Missouri state tax on crypto gains** (after Aug 28, 2025)
2. **Applies to ALL capital gains** (stocks, crypto, real estate)
3. **Both short-term and long-term gains** exempt
4. **Missouri is the only state** with this exemption (as of 2025)

### ⚠️ Important Notes

1. **Federal taxes still apply** - You must still file with the IRS
2. **You still need to track everything** - Cost basis, dates, amounts
3. **For 2025:** Split reporting between pre-exemption (Jan 1 - Aug 27) and post-exemption (Aug 28 - Dec 31)
4. **Consult a tax professional** - This is complex and rules may change

---

## Timeline

### Before August 28, 2025

Capital gains from cryptocurrency were taxed as part of Missouri income tax:

- Reported on **Form MO-1040**
- Taxed at Missouri income tax rates (up to 5.4%)
- Followed federal capital gains classification

### After August 28, 2025

Capital gains from cryptocurrency are **100% EXEMPT** from Missouri state tax:

- Still report on **Form MO-1040** (Line 6 adjustment)
- File **Form MO-A** (Missouri Adjustments) to claim exemption
- Pay **$0** Missouri state tax on crypto gains

### Federal (All Years)

Capital gains from cryptocurrency are taxed by the IRS:

- File **Form 8949** (Sales and Other Dispositions of Capital Assets)
- File **Schedule D** (Capital Gains and Losses)
- Include on **Form 1040**
- Pay federal capital gains tax (0%, 15%, or 20% for long-term)

---

## How CARBS Helps

CARBS automatically tracks everything you need for Missouri tax compliance:

### 1. Cost Basis Tracking

```python
from compliance.cost_basis import CostBasisTracker, CostBasisMethod

# Track cost basis using your preferred method
tracker = CostBasisTracker(method=CostBasisMethod.FIFO)

# System automatically tracks:
# - Acquisition date
# - Acquisition cost
# - Holding period
# - Disposition date
# - Gain/loss calculation
```

### 2. Missouri Tax Calculation

```python
from compliance.missouri_tax import MissouriTaxCalculator

calculator = MissouriTaxCalculator()

# Automatically determines if gain is exempt
result = calculator.calculate_missouri_tax(
    capital_gains=Decimal("1000.00"),
    transaction_date=datetime(2025, 12, 1),  # Post-exemption
    filing_status="single"
)

# result = {
#     "taxable_amount": Decimal("0"),  # Exempt!
#     "exempt_amount": Decimal("1000.00"),
#     "estimated_mo_tax": Decimal("0"),
#     "notes": "100% exempt under Missouri capital gains tax repeal..."
# }
```

### 3. Form Generation

```python
from compliance.missouri_tax import export_missouri_tax_package

# Generate complete Missouri tax package
package = export_missouri_tax_package(
    dispositions=my_dispositions,  # From CostBasisTracker
    tax_year=2025,
    taxpayer_info={
        "name": "Your Name",
        "ssn_last4": "1234"
    }
)

# Generated files:
# - MO-A_Worksheet_2025.txt (Form MO-A helper)
# - Missouri_Tax_Summary_2025.txt (for your accountant)
```

---

## Example: 2025 Tax Scenario

### Scenario

You made these crypto trades in 2025:

| Date | Trade | Gain/Loss |
|------|-------|-----------|
| March 15, 2025 | Sold 0.1 BTC | +$500 gain |
| September 10, 2025 | Sold 0.5 ETH | +$800 gain |
| December 1, 2025 | Sold 1.0 ETH | +$1,200 gain |

**Total gains:** $2,500

### Tax Calculation

**Missouri State Tax:**

- March 15 gain ($500): Pre-exemption, taxable in Missouri
  - Estimated MO tax: $500 × 5.4% = **$27**
- September 10 gain ($800): Post-exemption, **EXEMPT**
- December 1 gain ($1,200): Post-exemption, **EXEMPT**

**Total Missouri tax:** **$27** (only on March gain)

**Federal Tax:**

- All gains taxable federally: $2,500
- If long-term (>1 year): $2,500 × 15% = **$375**
- If short-term (<1 year): $2,500 × 22% (example) = **$550**

**Total Federal tax:** **$375 - $550** (depending on holding period)

### Forms to File

**Missouri:**
1. Form MO-1040 (Individual Income Tax Return)
2. Form MO-A (claim $2,000 exemption for post-Aug 28 gains)

**Federal:**
1. Form 8949 (detail all transactions)
2. Schedule D (summarize capital gains)
3. Form 1040

---

## Step-by-Step Filing Guide

### Step 1: Export Your Data

```bash
# In CARBS directory
python scripts/export_missouri_tax.py --year 2025

# This generates:
# - data/exports/missouri/MO-A_Worksheet_2025.txt
# - data/exports/missouri/Missouri_Tax_Summary_2025.txt
# - data/exports/trades_2025.csv
# - data/exports/form_8949_2025.csv
```

### Step 2: Review Your Gains

Open `Missouri_Tax_Summary_2025.txt` and verify:

- Total capital gains match your records
- Pre-exemption vs. post-exemption split is correct
- Federal tax estimate seems reasonable

### Step 3: Provide to Your Accountant

Give your CPA/tax preparer:

1. `Missouri_Tax_Summary_2025.txt`
2. `MO-A_Worksheet_2025.txt`
3. `trades_2025.csv`
4. `form_8949_2025.csv`

Tell them: "Missouri eliminated capital gains tax on August 28, 2025. These files show my crypto trades for the year."

### Step 4: File Your Returns

Your tax preparer will:

**Missouri:**
- Complete Form MO-1040
- Complete Form MO-A (capital gains adjustment)
- Apply 100% exemption for post-Aug 28 gains
- Calculate minimal tax on pre-Aug 28 gains (if any)

**Federal:**
- Complete Form 8949 (list all transactions)
- Complete Schedule D (summarize gains/losses)
- Include on Form 1040
- Calculate federal tax owed

### Step 5: Pay Taxes (if any)

- **Missouri:** Likely $0 or very small (only pre-Aug 28 gains)
- **Federal:** Standard capital gains rates

---

## Frequently Asked Questions

### Q: Do I still need to track my crypto trades?

**A:** YES! Even though Missouri doesn't tax capital gains, the IRS still does. You must track:
- Every purchase and sale
- Dates and amounts
- Cost basis
- Gains and losses

CARBS does this automatically.

### Q: What if I moved to Missouri in 2025?

**A:** You're a part-year resident. You'll need to prorate your Missouri income:
- Gains while MO resident: Apply MO exemption (if post-Aug 28)
- Gains while resident of other state: Follow that state's rules

Consult a tax professional familiar with part-year returns.

### Q: Can I use the Missouri exemption if I'm not a Missouri resident?

**A:** No. The exemption only applies to:
- Missouri residents
- Missouri-sourced income for nonresidents (rare for crypto)

If you're not a Missouri resident, your home state's rules apply.

### Q: What about crypto staking rewards or airdrops?

**A:** These are generally treated as ordinary income, not capital gains:
- **Federal:** Taxable as ordinary income when received
- **Missouri:** Taxable as ordinary income (no capital gains exemption applies)

However, when you later SELL the staked coins or airdropped tokens, any gain/loss IS a capital gain (exempt in Missouri post-Aug 28, 2025).

### Q: Does this apply to NFTs?

**A:** Yes! NFTs are treated as property/capital assets. Gains from NFT sales are capital gains, so the Missouri exemption applies.

### Q: What if Missouri reinstates the capital gains tax?

**A:** Unlikely in near term, but possible in future. Monitor:
- Missouri Department of Revenue website
- Your tax professional's updates
- CARBS will be updated if rules change

---

## Resources

### Missouri

- **Missouri Department of Revenue:** [dor.mo.gov](https://dor.mo.gov/)
- **Form MO-1040:** [Download from DOR](https://dor.mo.gov/forms/MO-1040_2025.pdf)
- **Form MO-A:** [Download from DOR](https://dor.mo.gov/forms/MO-A_2025.pdf)
- **Missouri Tax Rate Schedule:** [View rates](https://dor.mo.gov/taxation/individual/tax-rates/)

### Federal (IRS)

- **Cryptocurrency Guidance:** [IRS.gov/crypto](https://www.irs.gov/businesses/small-businesses-self-employed/virtual-currencies)
- **Form 8949:** [Download from IRS](https://www.irs.gov/pub/irs-pdf/f8949.pdf)
- **Schedule D:** [Download from IRS](https://www.irs.gov/pub/irs-pdf/f1040sd.pdf)
- **Publication 544 (Sales and Other Dispositions of Assets):** [Download](https://www.irs.gov/pub/irs-pdf/p544.pdf)

### Tax Professionals

- **Find a Missouri CPA:** [Missouri Society of CPAs](https://www.mocpa.org/)
- **Find a crypto tax specialist:** [CryptoTaxCalculator Directory](https://cryptotaxcalculator.io/tax-accountants/)

---

## Disclaimer

This guide is for informational purposes only and does not constitute tax advice. Tax laws are complex and subject to change. Consult with a qualified Missouri tax professional or CPA before making tax decisions.

**The author(s) of CARBS are not responsible for any tax liabilities, penalties, or errors in tax reporting.**

---

## Updates

**2025-12-17:** Initial version created
- Documented Missouri capital gains exemption (effective Aug 28, 2025)
- Created Missouri tax module in CARBS
- Added form generation capabilities

---

**Questions?** Open an issue on GitHub or consult a Missouri tax professional.
