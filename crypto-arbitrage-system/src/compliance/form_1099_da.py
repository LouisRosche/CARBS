"""
Form 1099-DA Reconciliation Module

Starting in tax year 2025 (filed in 2026), cryptocurrency exchanges are required
to issue Form 1099-DA reporting gross proceeds from digital asset sales.

This module helps reconcile exchange-reported data with your internal records
to identify discrepancies and ensure accurate tax reporting.

Background:
- Infrastructure Investment and Jobs Act (2021) requires broker reporting
- Applies to tax years beginning after December 31, 2025
- Exchanges must report: Gross proceeds, cost basis (if known), date acquired/sold
- Taxpayers must reconcile 1099-DA with their own records

References:
- IRS Form 1099-DA: https://www.irs.gov/forms-pubs/about-form-1099-da
- Notice 2023-10: Digital Asset Broker Reporting
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import csv
import json


@dataclass
class Form1099DA:
    """
    Represents a 1099-DA form received from an exchange

    Mirrors the structure of IRS Form 1099-DA
    """
    # Payer (Exchange) Information
    payer_name: str  # e.g., "Binance.US"
    payer_tin: str  # Exchange's EIN
    payer_address: str

    # Recipient (Taxpayer) Information
    recipient_name: str
    recipient_ssn: str  # Last 4 digits only for security
    recipient_address: str

    # Account Information
    account_number: str  # Exchange account identifier
    tax_year: int

    # Box 1: Gross proceeds from digital asset sales
    gross_proceeds: Decimal

    # Box 2: Cost basis (if exchange has records)
    cost_basis: Optional[Decimal] = None

    # Box 3: Gain/Loss (if both gross proceeds and cost basis provided)
    gain_loss: Optional[Decimal] = None

    # Box 4: Check if cost basis is unavailable
    cost_basis_unavailable: bool = False

    # Detailed transactions (if provided)
    transactions: List[Dict] = field(default_factory=list)

    # Form metadata
    form_id: Optional[str] = None  # Unique identifier from exchange
    date_received: Optional[datetime] = None
    corrected_form: bool = False  # Is this a corrected 1099-DA?


@dataclass
class ReconciliationDiscrepancy:
    """Represents a discrepancy between 1099-DA and internal records"""

    transaction_id: str
    exchange: str
    asset: str
    date: datetime

    # What the exchange reported
    exchange_proceeds: Optional[Decimal] = None
    exchange_cost_basis: Optional[Decimal] = None

    # What your records show
    carbs_proceeds: Optional[Decimal] = None
    carbs_cost_basis: Optional[Decimal] = None

    # Difference
    proceeds_difference: Optional[Decimal] = None
    basis_difference: Optional[Decimal] = None

    # Impact on taxes
    tax_impact: Optional[Decimal] = None  # Positive = you owe more, Negative = you owe less

    # Explanation
    discrepancy_type: str = "unknown"  # 'missing_transaction', 'amount_mismatch', 'date_mismatch', 'basis_error'
    notes: str = ""

    # Resolution
    resolved: bool = False
    resolution_action: str = ""  # What to do about it


@dataclass
class ReconciliationReport:
    """Complete reconciliation report comparing 1099-DA to internal records"""

    tax_year: int
    exchange: str
    date_generated: datetime

    # Summary statistics
    total_1099da_proceeds: Decimal
    total_carbs_proceeds: Decimal
    proceeds_difference: Decimal

    total_1099da_cost_basis: Optional[Decimal] = None
    total_carbs_cost_basis: Optional[Decimal] = None
    basis_difference: Optional[Decimal] = None

    # Transactions that match
    matched_transactions: int = 0
    matched_proceeds: Decimal = Decimal("0")

    # Discrepancies found
    discrepancies: List[ReconciliationDiscrepancy] = field(default_factory=list)

    # Transactions in CARBS but not on 1099-DA
    missing_from_1099da: List[Dict] = field(default_factory=list)

    # Transactions on 1099-DA but not in CARBS
    missing_from_carbs: List[Dict] = field(default_factory=list)

    # Recommendation
    recommendation: str = ""
    requires_amended_return: bool = False


class Form1099DAReconciler:
    """
    Reconciles Form 1099-DA data from exchanges with internal CARBS records

    Helps identify:
    - Transactions the exchange didn't report
    - Transactions you don't have records for
    - Cost basis errors
    - Gross proceeds discrepancies
    """

    def __init__(self, carbs_database):
        """
        Initialize reconciler

        Args:
            carbs_database: Database connection to CARBS trade records
        """
        self.db = carbs_database

    def import_1099da_csv(self, file_path: Path) -> Form1099DA:
        """
        Import Form 1099-DA data from CSV file

        Expected CSV format:
        PayerName,PayerTIN,AccountNumber,TaxYear,GrossProceeds,CostBasis,CostBasisUnavailable

        Or detailed transaction format:
        Date,Asset,Quantity,Proceeds,CostBasis,GainLoss

        Args:
            file_path: Path to CSV file

        Returns:
            Form1099DA object
        """
        # Implementation would parse CSV
        # This is a placeholder showing the structure
        raise NotImplementedError("Import from your exchange's specific CSV format")

    def reconcile_exchange(
        self,
        form_1099da: Form1099DA,
        tax_year: int,
        exchange: str
    ) -> ReconciliationReport:
        """
        Reconcile a Form 1099-DA against CARBS records

        Args:
            form_1099da: The 1099-DA form data
            tax_year: Tax year to reconcile
            exchange: Exchange name (e.g., 'binance', 'mexc')

        Returns:
            ReconciliationReport with all discrepancies
        """
        report = ReconciliationReport(
            tax_year=tax_year,
            exchange=exchange,
            date_generated=datetime.now(),
            total_1099da_proceeds=form_1099da.gross_proceeds,
            total_carbs_proceeds=Decimal("0"),
            proceeds_difference=Decimal("0")
        )

        # Get CARBS records for this exchange and year
        carbs_trades = self._get_carbs_trades(exchange, tax_year)

        # Calculate CARBS totals
        carbs_proceeds = sum(
            Decimal(str(trade.get('proceeds', 0)))
            for trade in carbs_trades
        )
        carbs_cost_basis = sum(
            Decimal(str(trade.get('cost_basis', 0)))
            for trade in carbs_trades
        )

        report.total_carbs_proceeds = carbs_proceeds
        report.total_carbs_cost_basis = carbs_cost_basis
        report.proceeds_difference = carbs_proceeds - form_1099da.gross_proceeds

        if form_1099da.cost_basis:
            report.total_1099da_cost_basis = form_1099da.cost_basis
            report.basis_difference = carbs_cost_basis - form_1099da.cost_basis

        # Match transactions
        if form_1099da.transactions:
            self._match_transactions(
                form_1099da.transactions,
                carbs_trades,
                report
            )

        # Generate recommendation
        self._generate_recommendation(report)

        return report

    def _get_carbs_trades(self, exchange: str, tax_year: int) -> List[Dict]:
        """
        Get all CARBS trades for an exchange in a tax year

        Args:
            exchange: Exchange name
            tax_year: Tax year

        Returns:
            List of trade dictionaries
        """
        # This would query the CARBS database
        # Placeholder implementation
        return []

    def _match_transactions(
        self,
        exchange_txns: List[Dict],
        carbs_txns: List[Dict],
        report: ReconciliationReport
    ):
        """
        Match transactions between 1099-DA and CARBS records

        Matching criteria:
        - Date (within 24 hours)
        - Asset
        - Quantity (within 1%)
        - Exchange

        Args:
            exchange_txns: Transactions from 1099-DA
            carbs_txns: Transactions from CARBS
            report: Report to populate with findings
        """
        matched_exchange_ids = set()
        matched_carbs_ids = set()

        for ex_txn in exchange_txns:
            for carbs_txn in carbs_txns:
                if self._transactions_match(ex_txn, carbs_txn):
                    # Check for amount discrepancies
                    if not self._amounts_match(ex_txn, carbs_txn):
                        discrepancy = self._create_discrepancy(
                            ex_txn, carbs_txn, "amount_mismatch"
                        )
                        report.discrepancies.append(discrepancy)
                    else:
                        report.matched_transactions += 1
                        report.matched_proceeds += Decimal(str(ex_txn.get('proceeds', 0)))

                    matched_exchange_ids.add(id(ex_txn))
                    matched_carbs_ids.add(id(carbs_txn))
                    break

        # Find unmatched transactions
        for ex_txn in exchange_txns:
            if id(ex_txn) not in matched_exchange_ids:
                report.missing_from_carbs.append(ex_txn)

        for carbs_txn in carbs_txns:
            if id(carbs_txn) not in matched_carbs_ids:
                report.missing_from_1099da.append(carbs_txn)

    def _transactions_match(self, ex_txn: Dict, carbs_txn: Dict) -> bool:
        """Check if two transactions are the same trade"""
        # Match on date (within 24 hours), asset, and quantity (within 1%)
        date_match = abs(
            (ex_txn['date'] - carbs_txn['date']).total_seconds()
        ) < 86400

        asset_match = ex_txn['asset'] == carbs_txn['asset']

        qty_diff = abs(
            Decimal(str(ex_txn['quantity'])) - Decimal(str(carbs_txn['quantity']))
        )
        qty_tolerance = Decimal(str(ex_txn['quantity'])) * Decimal("0.01")
        quantity_match = qty_diff <= qty_tolerance

        return date_match and asset_match and quantity_match

    def _amounts_match(self, ex_txn: Dict, carbs_txn: Dict) -> bool:
        """Check if transaction amounts match"""
        proceeds_diff = abs(
            Decimal(str(ex_txn.get('proceeds', 0))) -
            Decimal(str(carbs_txn.get('proceeds', 0)))
        )

        # Allow 1 cent difference (rounding)
        proceeds_match = proceeds_diff <= Decimal("0.01")

        if ex_txn.get('cost_basis') and carbs_txn.get('cost_basis'):
            basis_diff = abs(
                Decimal(str(ex_txn['cost_basis'])) -
                Decimal(str(carbs_txn['cost_basis']))
            )
            basis_match = basis_diff <= Decimal("0.01")
        else:
            basis_match = True  # Can't compare if one is missing

        return proceeds_match and basis_match

    def _create_discrepancy(
        self,
        ex_txn: Dict,
        carbs_txn: Dict,
        discrepancy_type: str
    ) -> ReconciliationDiscrepancy:
        """Create a discrepancy record"""
        ex_proceeds = Decimal(str(ex_txn.get('proceeds', 0)))
        carbs_proceeds = Decimal(str(carbs_txn.get('proceeds', 0)))
        proceeds_diff = carbs_proceeds - ex_proceeds

        ex_basis = Decimal(str(ex_txn.get('cost_basis', 0))) if ex_txn.get('cost_basis') else None
        carbs_basis = Decimal(str(carbs_txn.get('cost_basis', 0))) if carbs_txn.get('cost_basis') else None

        if ex_basis and carbs_basis:
            basis_diff = carbs_basis - ex_basis
            # Tax impact: if your basis is higher, you owe less tax
            # If proceeds are higher, you owe more tax
            tax_impact = proceeds_diff - basis_diff
        else:
            basis_diff = None
            tax_impact = proceeds_diff  # Conservative: assume basis is correct

        return ReconciliationDiscrepancy(
            transaction_id=carbs_txn.get('id', 'unknown'),
            exchange=carbs_txn.get('exchange', 'unknown'),
            asset=carbs_txn.get('asset', 'unknown'),
            date=carbs_txn.get('date', datetime.now()),
            exchange_proceeds=ex_proceeds,
            exchange_cost_basis=ex_basis,
            carbs_proceeds=carbs_proceeds,
            carbs_cost_basis=carbs_basis,
            proceeds_difference=proceeds_diff,
            basis_difference=basis_diff,
            tax_impact=tax_impact,
            discrepancy_type=discrepancy_type
        )

    def _generate_recommendation(self, report: ReconciliationReport):
        """Generate recommendation based on reconciliation findings"""

        # Thresholds for concern
        MATERIAL_DIFFERENCE = Decimal("100.00")  # $100
        MANY_DISCREPANCIES = 10

        total_discrepancies = len(report.discrepancies)
        total_missing_from_1099da = len(report.missing_from_1099da)
        total_missing_from_carbs = len(report.missing_from_carbs)

        # Perfect match
        if (total_discrepancies == 0 and
            total_missing_from_1099da == 0 and
            total_missing_from_carbs == 0 and
            abs(report.proceeds_difference) < Decimal("1.00")):

            report.recommendation = (
                "✅ PERFECT MATCH: Your CARBS records match the 1099-DA from "
                f"{report.exchange}. No action required. File your taxes using "
                "either CARBS data or 1099-DA data (they agree)."
            )
            report.requires_amended_return = False
            return

        # Minor differences (likely rounding)
        if (total_discrepancies == 0 and
            abs(report.proceeds_difference) < MATERIAL_DIFFERENCE):

            report.recommendation = (
                f"✅ MINOR DIFFERENCE: Your CARBS records differ from the 1099-DA "
                f"by ${abs(report.proceeds_difference):.2f}. This is likely due to "
                "rounding differences. Use the 1099-DA amounts for tax filing to "
                "match IRS records. No amended return needed."
            )
            report.requires_amended_return = False
            return

        # Material differences
        if abs(report.proceeds_difference) >= MATERIAL_DIFFERENCE:
            report.recommendation = (
                f"⚠️ MATERIAL DIFFERENCE: Your CARBS records differ from the 1099-DA "
                f"by ${abs(report.proceeds_difference):.2f}. "
            )

            if report.proceeds_difference > 0:
                report.recommendation += (
                    "Your records show MORE proceeds than the exchange reported. "
                    "You should use YOUR records (CARBS) and attach Form 8275 "
                    "(Disclosure Statement) explaining the discrepancy. The IRS "
                    "expects your return to match the 1099-DA, so document why it doesn't."
                )
            else:
                report.recommendation += (
                    "The exchange reported MORE proceeds than your records show. "
                    "This means you may be missing transactions. Review the "
                    "'missing_from_carbs' list and update your records. Use the "
                    "1099-DA amounts for filing."
                )

            report.requires_amended_return = False  # Not amended, just reconcile first

        # Many discrepancies
        if total_discrepancies >= MANY_DISCREPANCIES:
            report.recommendation += (
                f"\n\n🚨 MANY DISCREPANCIES: Found {total_discrepancies} transactions "
                "with mismatched amounts. Review each discrepancy in detail. "
                "Common causes: "
                "1) Exchange using different cost basis method (FIFO vs HIFO)"
                "2) Fees calculated differently"
                "3) Exchange missing some of your transaction history"
                "\n\nRecommendation: Contact a tax professional before filing."
            )
            report.requires_amended_return = False

        # Transactions missing from 1099-DA
        if total_missing_from_1099da > 0:
            report.recommendation += (
                f"\n\n⚠️ UNREPORTED TRANSACTIONS: You have {total_missing_from_1099da} "
                "transactions in CARBS that are NOT on the 1099-DA. Possible reasons:"
                "\n1) These trades occurred on a different exchange"
                "\n2) The exchange's reporting threshold wasn't met for these"
                "\n3) The exchange made an error"
                "\n\nYou MUST report ALL transactions even if not on 1099-DA. "
                "Use CARBS data for these trades."
            )

        # Transactions missing from CARBS
        if total_missing_from_carbs > 0:
            report.recommendation += (
                f"\n\n🚨 MISSING RECORDS: The 1099-DA includes {total_missing_from_carbs} "
                "transactions that are NOT in your CARBS database. This is serious. "
                "You need to:"
                "\n1) Download complete trade history from exchange"
                "\n2) Import missing trades into CARBS"
                "\n3) Recalculate cost basis for ALL trades"
                "\n4) Re-run this reconciliation"
                "\n\nDO NOT file until your records are complete."
            )
            report.requires_amended_return = False  # Get it right the first time

    def export_reconciliation_report(
        self,
        report: ReconciliationReport,
        output_dir: Path
    ) -> Path:
        """
        Export reconciliation report to CSV and JSON

        Args:
            report: ReconciliationReport to export
            output_dir: Directory for output files

        Returns:
            Path to summary file
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Summary JSON
        summary_file = output_dir / f"1099DA_reconciliation_{report.exchange}_{report.tax_year}.json"
        summary_data = {
            'tax_year': report.tax_year,
            'exchange': report.exchange,
            'date_generated': report.date_generated.isoformat(),
            'summary': {
                '1099da_proceeds': str(report.total_1099da_proceeds),
                'carbs_proceeds': str(report.total_carbs_proceeds),
                'difference': str(report.proceeds_difference),
                'matched_transactions': report.matched_transactions,
                'discrepancies_count': len(report.discrepancies),
                'missing_from_1099da': len(report.missing_from_1099da),
                'missing_from_carbs': len(report.missing_from_carbs)
            },
            'recommendation': report.recommendation,
            'requires_amended_return': report.requires_amended_return
        }

        with open(summary_file, 'w') as f:
            json.dump(summary_data, f, indent=2)

        # Discrepancies CSV
        if report.discrepancies:
            discrepancies_file = output_dir / f"1099DA_discrepancies_{report.exchange}_{report.tax_year}.csv"
            with open(discrepancies_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Transaction ID', 'Exchange', 'Asset', 'Date',
                    'Exchange Proceeds', 'CARBS Proceeds', 'Proceeds Difference',
                    'Exchange Cost Basis', 'CARBS Cost Basis', 'Basis Difference',
                    'Tax Impact', 'Discrepancy Type', 'Notes'
                ])

                for disc in report.discrepancies:
                    writer.writerow([
                        disc.transaction_id,
                        disc.exchange,
                        disc.asset,
                        disc.date.strftime('%Y-%m-%d'),
                        disc.exchange_proceeds,
                        disc.carbs_proceeds,
                        disc.proceeds_difference,
                        disc.exchange_cost_basis or '',
                        disc.carbs_cost_basis or '',
                        disc.basis_difference or '',
                        disc.tax_impact or '',
                        disc.discrepancy_type,
                        disc.notes
                    ])

        return summary_file


def reconcile_all_exchanges(tax_year: int, forms_directory: Path) -> Dict[str, ReconciliationReport]:
    """
    Reconcile Form 1099-DA from all exchanges for a tax year

    Args:
        tax_year: Tax year to reconcile
        forms_directory: Directory containing 1099-DA files

    Returns:
        Dictionary mapping exchange name to ReconciliationReport
    """
    # Implementation would:
    # 1. Find all 1099-DA files in directory
    # 2. Parse each file
    # 3. Run reconciliation for each exchange
    # 4. Generate combined report
    # 5. Export results

    raise NotImplementedError("Implement based on your 1099-DA file naming convention")


# Example usage:
if __name__ == "__main__":
    """
    Example: How to use the Form 1099-DA reconciliation module

    This is for demonstration and will need to be customized for your
    exchange's specific 1099-DA format.
    """

    from pathlib import Path

    # Example: You received a 1099-DA from Binance.US for tax year 2025
    # (This would be received in early 2026)

    # Step 1: Create the Form1099DA object from your exchange's data
    # In practice, you'd import this from a CSV or PDF provided by the exchange

    binance_1099da = Form1099DA(
        payer_name="Binance.US",
        payer_tin="XX-XXXXXXX",  # Exchange's EIN
        payer_address="555 California St, San Francisco, CA 94104",
        recipient_name="Your Name",
        recipient_ssn="XXXX",  # Last 4 digits
        recipient_address="Your Address",
        account_number="BINANCE123456",
        tax_year=2025,
        gross_proceeds=Decimal("15000.00"),  # What they say you sold
        cost_basis=Decimal("12000.00"),  # What they think you paid
        gain_loss=Decimal("3000.00"),  # Their calculation
        cost_basis_unavailable=False
    )

    # Step 2: Initialize the reconciler with your CARBS database
    # reconciler = Form1099DAReconciler(carbs_database_connection)

    # Step 3: Run reconciliation
    # report = reconciler.reconcile_exchange(binance_1099da, 2025, "binance")

    # Step 4: Review the report
    # print(report.recommendation)
    # print(f"Matched: {report.matched_transactions} transactions")
    # print(f"Discrepancies: {len(report.discrepancies)}")

    # Step 5: Export for your tax professional
    # summary_file = reconciler.export_reconciliation_report(
    #     report,
    #     Path("tax_documents/2025")
    # )

    print("Form 1099-DA reconciliation module loaded.")
    print("Customize the import functions for your exchange's specific format.")
    print("This will be critical starting with 2025 tax year (filed in 2026).")
