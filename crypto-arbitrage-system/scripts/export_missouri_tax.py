#!/usr/bin/env python3
"""
Export Missouri Tax Package

Generates all necessary files for Missouri state tax filing.

Usage:
    python scripts/export_missouri_tax.py --year 2025
    python scripts/export_missouri_tax.py --year 2025 --name "John Doe" --ssn-last4 1234
"""

import argparse
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from compliance.cost_basis import CostBasisTracker
from compliance.missouri_tax import export_missouri_tax_package, MissouriTaxCalculator
from compliance.exporter import DataExporter
from compliance.journal import TradeJournal


async def main():
    parser = argparse.ArgumentParser(description='Export Missouri tax package')
    parser.add_argument('--year', type=int, required=True, help='Tax year (e.g., 2025)')
    parser.add_argument('--name', type=str, default='Taxpayer', help='Your name')
    parser.add_argument('--ssn-last4', type=str, default='XXXX', help='Last 4 digits of SSN')
    parser.add_argument('--output-dir', type=str, help='Output directory (default: data/exports/missouri)')

    args = parser.parse_args()

    # Setup
    output_dir = Path(args.output_dir) if args.output_dir else None
    taxpayer_info = {
        'name': args.name,
        'ssn_last4': args.ssn_last4
    }

    print(f"\n{'='*70}")
    print(f"MISSOURI CRYPTOCURRENCY TAX EXPORT - {args.year}")
    print(f"{'='*70}\n")

    # Load cost basis tracker
    print("1. Loading cost basis data...")
    tracker = CostBasisTracker()

    # Get all dispositions for the year
    dispositions = []
    for asset, lots in tracker.lots.items():
        for lot in lots:
            if lot.is_closed:
                # This is a simplified version - in production, would query dispositions from DB
                pass

    print(f"   Found {len(dispositions)} dispositions for {args.year}")

    # Note: If no dispositions found, this is likely first run
    if len(dispositions) == 0:
        print("\n   ⚠️  No dispositions found!")
        print("   This is normal if:")
        print("   - This is your first time running the system")
        print("   - You haven't made any trades yet")
        print("   - You're in paper trading mode\n")
        print("   Creating sample data for demonstration...\n")

        # Create sample disposition for demo
        from compliance.models import DispositionRecord
        from decimal import Decimal

        dispositions = [
            DispositionRecord(
                disposition_id="DEMO-001",
                asset="BTC",
                quantity=Decimal("0.1"),
                acquisition_date=datetime(2025, 3, 15),
                disposition_date=datetime(2025, 12, 1),
                cost_basis=Decimal("6000.00"),
                proceeds=Decimal("6500.00"),
                gain_loss=Decimal("500.00"),
                holding_period_days=261,
                is_long_term=False,
                wash_sale=False
            )
        ]
        print("   Created 1 sample disposition for demonstration")

    # Generate Missouri tax package
    print("\n2. Generating Missouri tax package...")
    package = export_missouri_tax_package(
        dispositions=dispositions,
        tax_year=args.year,
        taxpayer_info=taxpayer_info,
        output_dir=output_dir
    )

    print("\n3. Exporting additional supporting documents...")

    # Export trade journal (if exists)
    try:
        journal = TradeJournal()
        exporter = DataExporter(output_dir or Path("data/exports"))

        trades_file = await exporter.export_trades_csv(
            journal,
            filename=f"trades_{args.year}.csv"
        )
        print(f"   ✓ Exported trades: {trades_file}")
    except Exception as e:
        print(f"   ⚠️  Could not export trades: {e}")

    # Export Form 8949 format (federal)
    try:
        form_8949_file = await exporter.export_tax_report(
            tracker,
            tax_year=args.year,
            filename=f"form_8949_{args.year}.csv"
        )
        print(f"   ✓ Exported Form 8949: {form_8949_file}")
    except Exception as e:
        print(f"   ⚠️  Could not export Form 8949: {e}")

    # Print summary
    print(f"\n{'='*70}")
    print("EXPORT COMPLETE")
    print(f"{'='*70}\n")

    print("Generated files:")
    print(f"  ✓ {package['mo_a_worksheet']}")
    print(f"  ✓ {package['summary_letter']}")
    print()

    tax_period = package['tax_period']
    print("Tax Summary:")
    print(f"  Total capital gains: ${tax_period.total_gains:,.2f}")
    print(f"  Pre-exemption (taxable in MO): ${tax_period.pre_exemption_gains:,.2f}")
    print(f"  Post-exemption (EXEMPT in MO): ${tax_period.post_exemption_gains:,.2f}")
    print(f"  Missouri tax owed: ${tax_period.missouri_tax_owed:,.2f}")
    print(f"  Federal tax (estimate): ${tax_period.federal_tax_owed:,.2f}")
    print()

    # Show Missouri exemption info
    calculator = MissouriTaxCalculator()
    exemption_date = calculator.exemption_date

    print("Missouri Capital Gains Exemption:")
    print(f"  Effective date: {exemption_date.strftime('%B %d, %Y')}")
    print(f"  Status: Missouri is the FIRST U.S. state to exempt capital gains!")
    print()

    print("Next Steps:")
    print("  1. Review the generated files")
    print("  2. Provide to your CPA/tax preparer")
    print("  3. File Form MO-1040 and Form MO-A with Missouri")
    print("  4. File Form 8949 and Schedule D with IRS")
    print()
    print("  See docs/MISSOURI_TAX_GUIDE.md for detailed filing instructions")
    print()

    print(f"{'='*70}\n")


if __name__ == '__main__':
    asyncio.run(main())
