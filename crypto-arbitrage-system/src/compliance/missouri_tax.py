"""
Missouri State Tax Compliance Module

Handles Missouri-specific tax reporting for cryptocurrency trading.

MAJOR CHANGE FOR 2025:
As of August 28, 2025, Missouri became the first U.S. state to exempt
capital gains (including cryptocurrency) from state income tax.

Sources:
- https://fortune.com/2025/05/08/missouri-first-us-state-exempt-stock-crypto-sale-profits-income-taxes/
- https://www.kcur.org/politics-elections-and-government/2025-08-28/missouri-capital-gains-tax-repeal-income-stocks-real-estate-crypto
- https://chadgmann.com/2024/10/15/navigating-the-tax-labyrinth-understanding-cryptocurrency-taxes-in-missouri-and-federal-law/
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Missouri capital gains exemption effective date
MISSOURI_CAPITAL_GAINS_EXEMPTION_DATE = datetime(2025, 8, 28, tzinfo=timezone.utc)


@dataclass
class MissouriTaxPeriod:
    """Tax period for Missouri reporting"""
    year: int
    pre_exemption_gains: Decimal  # Jan 1 - Aug 27, 2025 (if 2025)
    post_exemption_gains: Decimal  # Aug 28+ 2025 (exempt)
    total_gains: Decimal
    federal_tax_owed: Decimal  # Federal taxes still apply
    missouri_tax_owed: Decimal  # $0 after Aug 28, 2025


class MissouriTaxCalculator:
    """
    Calculate Missouri state tax obligations for cryptocurrency trading

    Key Facts:
    - Before Aug 28, 2025: Capital gains taxed at Missouri income tax rates
    - After Aug 28, 2025: 100% capital gains exemption (MO becomes first state with this)
    - Federal taxes: Still apply (use Form 8949)
    - Forms needed: MO-1040, MO-A (for claiming exemption)
    """

    def __init__(self):
        self.exemption_date = MISSOURI_CAPITAL_GAINS_EXEMPTION_DATE

    def calculate_missouri_tax(
        self,
        capital_gains: Decimal,
        transaction_date: datetime,
        filing_status: str = "single"
    ) -> Dict[str, Decimal]:
        """
        Calculate Missouri state tax on cryptocurrency capital gains

        Args:
            capital_gains: Total capital gains for the transaction
            transaction_date: When the gain/loss was realized
            filing_status: Tax filing status (for pre-exemption calculations)

        Returns:
            Dict with:
            - taxable_amount: Amount subject to MO tax (0 if post-exemption)
            - exempt_amount: Amount exempt from MO tax
            - estimated_mo_tax: Missouri tax owed
            - notes: Explanation
        """
        # After Aug 28, 2025: 100% exempt
        if transaction_date >= self.exemption_date:
            return {
                "taxable_amount": Decimal("0"),
                "exempt_amount": capital_gains,
                "estimated_mo_tax": Decimal("0"),
                "notes": "100% exempt under Missouri capital gains tax repeal (effective Aug 28, 2025)"
            }

        # Before Aug 28, 2025: Taxed at Missouri income tax rates
        # Missouri has progressive tax rates (example for illustration)
        # Actual rates depend on total income - consult tax professional
        mo_tax_rate = Decimal("0.054")  # 5.4% top rate (simplified)

        estimated_tax = capital_gains * mo_tax_rate

        return {
            "taxable_amount": capital_gains,
            "exempt_amount": Decimal("0"),
            "estimated_mo_tax": estimated_tax,
            "notes": f"Taxable in Missouri (pre-exemption period). Estimated at {mo_tax_rate * 100}% rate. Consult tax professional for actual rate based on total income."
        }

    def generate_annual_summary(
        self,
        dispositions: List,  # List of DispositionRecord objects
        tax_year: int
    ) -> MissouriTaxPeriod:
        """
        Generate annual Missouri tax summary

        For 2025: Splits into pre-exemption and post-exemption periods
        For 2026+: All gains exempt
        For <2025: All gains taxable
        """
        pre_exemption = Decimal("0")
        post_exemption = Decimal("0")
        total = Decimal("0")

        for disp in dispositions:
            gain = disp.gain_loss
            total += gain

            if tax_year >= 2026:
                # All exempt in 2026+
                post_exemption += gain
            elif tax_year == 2025:
                # Split by exemption date
                if disp.disposition_date >= self.exemption_date:
                    post_exemption += gain
                else:
                    pre_exemption += gain
            else:
                # All taxable before 2025
                pre_exemption += gain

        # Calculate Missouri tax (only on pre-exemption gains)
        mo_tax = pre_exemption * Decimal("0.054") if pre_exemption > 0 else Decimal("0")

        # Federal tax still applies to all gains
        federal_tax = total * Decimal("0.20")  # Simplified estimate

        return MissouriTaxPeriod(
            year=tax_year,
            pre_exemption_gains=pre_exemption,
            post_exemption_gains=post_exemption,
            total_gains=total,
            federal_tax_owed=federal_tax,
            missouri_tax_owed=mo_tax
        )


class MissouriFormGenerator:
    """
    Generate Missouri state tax forms

    Forms:
    - MO-1040: Individual Income Tax Return
    - MO-A: Missouri Adjustments (for claiming capital gains exemption)
    """

    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("data/exports/missouri")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_mo_a_worksheet(
        self,
        tax_period: MissouriTaxPeriod,
        taxpayer_info: Dict
    ) -> Path:
        """
        Generate Form MO-A worksheet (capital gains deduction)

        This is a simplified version - actual Form MO-A is more complex.
        Consult with Missouri tax professional for filing.
        """
        filename = f"MO-A_Worksheet_{tax_period.year}.txt"
        filepath = self.output_dir / filename

        with open(filepath, 'w') as f:
            f.write("MISSOURI FORM MO-A WORKSHEET\n")
            f.write("Capital Gains Deduction\n")
            f.write(f"Tax Year: {tax_period.year}\n")
            f.write("=" * 60 + "\n\n")

            f.write(f"Taxpayer: {taxpayer_info.get('name', 'N/A')}\n")
            f.write(f"SSN: {taxpayer_info.get('ssn_last4', 'XXXX')}\n\n")

            f.write("CAPITAL GAINS SUMMARY\n")
            f.write("-" * 60 + "\n")
            f.write(f"Pre-exemption gains (Jan 1 - Aug 27, 2025): ${tax_period.pre_exemption_gains:,.2f}\n")
            f.write(f"Post-exemption gains (Aug 28+ 2025): ${tax_period.post_exemption_gains:,.2f}\n")
            f.write(f"Total capital gains: ${tax_period.total_gains:,.2f}\n\n")

            f.write("MISSOURI TAX CALCULATION\n")
            f.write("-" * 60 + "\n")
            f.write(f"Taxable in Missouri: ${tax_period.pre_exemption_gains:,.2f}\n")
            f.write(f"Exempt from Missouri tax: ${tax_period.post_exemption_gains:,.2f}\n")
            f.write(f"Estimated Missouri tax owed: ${tax_period.missouri_tax_owed:,.2f}\n\n")

            f.write("FEDERAL TAX (STILL APPLIES)\n")
            f.write("-" * 60 + "\n")
            f.write(f"Estimated federal tax: ${tax_period.federal_tax_owed:,.2f}\n")
            f.write("Note: File federal Form 8949 and Schedule D\n\n")

            f.write("IMPORTANT NOTES\n")
            f.write("-" * 60 + "\n")
            f.write("1. Missouri eliminated capital gains tax effective Aug 28, 2025\n")
            f.write("2. This is the FIRST state to do so for crypto/stocks/real estate\n")
            f.write("3. Federal taxes still apply - file Form 8949 with IRS\n")
            f.write("4. Attach this worksheet to Form MO-1040\n")
            f.write("5. Consult with Missouri tax professional for final filing\n\n")

            f.write("REFERENCES\n")
            f.write("-" * 60 + "\n")
            f.write("- Missouri SB692 (capital gains tax repeal legislation)\n")
            f.write("- Missouri Department of Revenue: dor.mo.gov\n")
            f.write("- IRS cryptocurrency guidance: irs.gov/crypto\n")

        logger.info(f"Generated MO-A worksheet: {filepath}")
        return filepath

    def generate_tax_summary_letter(
        self,
        tax_period: MissouriTaxPeriod,
        taxpayer_info: Dict
    ) -> Path:
        """
        Generate a summary letter for your accountant/CPA
        """
        filename = f"Missouri_Tax_Summary_{tax_period.year}.txt"
        filepath = self.output_dir / filename

        with open(filepath, 'w') as f:
            f.write("MISSOURI CRYPTOCURRENCY TAX SUMMARY\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 70 + "\n\n")

            f.write(f"Dear Tax Professional,\n\n")
            f.write(f"This letter summarizes cryptocurrency trading activity for:\n")
            f.write(f"Taxpayer: {taxpayer_info.get('name', 'N/A')}\n")
            f.write(f"Tax Year: {tax_period.year}\n\n")

            f.write("MISSOURI-SPECIFIC INFORMATION\n")
            f.write("-" * 70 + "\n")
            f.write("Missouri repealed capital gains tax effective August 28, 2025.\n")
            f.write("This is a HISTORIC change - Missouri is the first state to exempt\n")
            f.write("capital gains from stocks, crypto, and real estate from state tax.\n\n")

            f.write("GAINS BREAKDOWN\n")
            f.write("-" * 70 + "\n")
            f.write(f"Total capital gains (all year): ${tax_period.total_gains:,.2f}\n\n")

            if tax_period.year == 2025:
                f.write(f"  Pre-exemption (Jan 1 - Aug 27): ${tax_period.pre_exemption_gains:,.2f}\n")
                f.write(f"  Post-exemption (Aug 28 - Dec 31): ${tax_period.post_exemption_gains:,.2f}\n")
                f.write(f"    ^ 100% EXEMPT from Missouri state tax\n\n")
            elif tax_period.year >= 2026:
                f.write(f"  All gains: ${tax_period.total_gains:,.2f}\n")
                f.write(f"    ^ 100% EXEMPT from Missouri state tax\n\n")

            f.write("TAX OBLIGATIONS\n")
            f.write("-" * 70 + "\n")
            f.write(f"Missouri state tax owed: ${tax_period.missouri_tax_owed:,.2f}\n")
            f.write(f"Federal tax owed (estimate): ${tax_period.federal_tax_owed:,.2f}\n\n")

            f.write("FORMS TO FILE\n")
            f.write("-" * 70 + "\n")
            f.write("Missouri:\n")
            f.write("  - Form MO-1040 (Individual Income Tax Return)\n")
            f.write("  - Form MO-A (Missouri Adjustments - for capital gains exemption)\n\n")
            f.write("Federal:\n")
            f.write("  - Form 8949 (Sales and Other Dispositions of Capital Assets)\n")
            f.write("  - Schedule D (Capital Gains and Losses)\n")
            f.write("  - Form 1040 (Individual Income Tax Return)\n\n")

            f.write("SUPPORTING DOCUMENTATION\n")
            f.write("-" * 70 + "\n")
            f.write("The following files are attached:\n")
            f.write("  - trades_[date].csv: All trades for the year\n")
            f.write("  - tax_lots_[date].json: Cost basis tracking\n")
            f.write("  - dispositions_[date].csv: Capital gains/losses detail\n")
            f.write("  - form_8949_[date].csv: Federal Form 8949 compatible format\n\n")

            f.write("Please let me know if you need any additional information.\n\n")
            f.write("Best regards,\n")
            f.write(f"{taxpayer_info.get('name', 'Taxpayer')}\n")

        logger.info(f"Generated tax summary letter: {filepath}")
        return filepath


# Convenience function
def export_missouri_tax_package(
    dispositions: List,
    tax_year: int,
    taxpayer_info: Dict,
    output_dir: Path = None
) -> Dict[str, Path]:
    """
    Export complete Missouri tax package

    Returns paths to all generated files:
    - mo_a_worksheet: Form MO-A worksheet
    - summary_letter: Summary for accountant
    """
    calculator = MissouriTaxCalculator()
    form_gen = MissouriFormGenerator(output_dir)

    # Calculate summary
    tax_period = calculator.generate_annual_summary(dispositions, tax_year)

    # Generate forms
    mo_a = form_gen.generate_mo_a_worksheet(tax_period, taxpayer_info)
    summary = form_gen.generate_tax_summary_letter(tax_period, taxpayer_info)

    return {
        "mo_a_worksheet": mo_a,
        "summary_letter": summary,
        "tax_period": tax_period
    }
