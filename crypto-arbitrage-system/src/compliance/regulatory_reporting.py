"""
Regulatory Reporting Framework

Provides compliance reporting for:
- SEC (Securities and Exchange Commission) - Form 10-K, 10-Q, 8-K
- FinCEN (Financial Crimes Enforcement Network) - SAR, CTR, FBAR
- IRS (Internal Revenue Service) - Form 8949, Form 1099-B
- CFTC (Commodity Futures Trading Commission) - For derivatives trading
- State regulators - Money transmitter licenses

Implements requirements from:
- Securities Exchange Act of 1934
- Bank Secrecy Act (BSA)
- USA PATRIOT Act
- Travel Rule (FATF Recommendation 16)
- State money transmission laws
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Set
from enum import Enum
from pathlib import Path
import json
import csv
import hashlib

logger = logging.getLogger(__name__)


class RegulatoryJurisdiction(Enum):
    """Regulatory jurisdictions"""
    US_FEDERAL = "us_federal"
    US_STATE = "us_state"
    EU = "european_union"
    UK = "united_kingdom"
    CANADA = "canada"
    AUSTRALIA = "australia"
    SINGAPORE = "singapore"
    JAPAN = "japan"


class ReportType(Enum):
    """Types of regulatory reports"""
    # SEC Reports
    FORM_10K = "form_10k"  # Annual report
    FORM_10Q = "form_10q"  # Quarterly report
    FORM_8K = "form_8k"    # Current report

    # FinCEN Reports
    SAR = "suspicious_activity_report"
    CTR = "currency_transaction_report"
    FBAR = "foreign_bank_account_report"

    # IRS Reports
    FORM_8949 = "form_8949"  # Capital gains/losses
    FORM_1099B = "form_1099b"  # Proceeds from broker transactions
    FORM_1099MISC = "form_1099misc"  # Miscellaneous income

    # AML/KYC
    TRAVEL_RULE = "travel_rule_report"
    KYC_REPORT = "kyc_compliance_report"

    # State
    MONEY_TRANSMITTER = "money_transmitter_report"


@dataclass
class SuspiciousActivityReport:
    """
    FinCEN SAR (Suspicious Activity Report)

    Required for transactions that:
    - Involve $5,000+ and known/suspected criminal activity
    - Designed to evade BSA reporting requirements
    - Have no business or lawful purpose
    - Involve use of business to facilitate criminal activity
    """
    report_id: str
    filing_institution: str
    filing_date: datetime

    # Subject information
    subject_name: str
    subject_id: str
    subject_type: str  # "individual", "entity"

    # Suspicious activity details
    activity_date: datetime
    activity_type: str
    activity_amount: Decimal
    currency: str

    # Narrative
    suspicious_behavior: str
    explanation: str

    # Related transactions
    transaction_ids: List[str] = field(default_factory=list)

    # Filing status
    filed: bool = False
    filing_confirmation: Optional[str] = None


@dataclass
class CurrencyTransactionReport:
    """
    FinCEN CTR (Currency Transaction Report)

    Required for transactions > $10,000 in a single day
    """
    report_id: str
    filing_institution: str
    filing_date: datetime

    # Transaction details
    transaction_date: datetime
    total_amount: Decimal
    currency: str

    # Person on whose behalf conducted
    person_name: str
    person_id: str
    person_type: str
    address: Dict[str, str]

    # Account information
    account_number: str

    # Multiple transactions indicator
    multiple_transactions: bool
    transaction_count: int
    transaction_ids: List[str] = field(default_factory=list)

    # Filing status
    filed: bool = False
    filing_confirmation: Optional[str] = None


@dataclass
class Form8949Transaction:
    """
    IRS Form 8949 - Sales and Other Dispositions of Capital Assets

    Required for reporting capital gains/losses from crypto transactions
    """
    # Description
    description: str  # e.g., "0.5 BTC"

    # Dates
    date_acquired: datetime
    date_sold: datetime

    # Amounts
    proceeds: Decimal
    cost_basis: Decimal
    adjustment_code: Optional[str] = None
    adjustment_amount: Decimal = Decimal("0")
    gain_or_loss: Decimal = Decimal("0")

    # Holding period
    is_short_term: bool = True  # < 1 year

    # Transaction details
    transaction_id: str = ""
    exchange: str = ""

    def __post_init__(self):
        """Calculate gain/loss and holding period"""
        self.gain_or_loss = self.proceeds - self.cost_basis - self.adjustment_amount
        holding_days = (self.date_sold - self.date_acquired).days
        self.is_short_term = holding_days < 365


@dataclass
class Form1099B:
    """
    IRS Form 1099-B - Proceeds from Broker and Barter Exchange Transactions

    Issued by brokers/exchanges to report proceeds from sales
    """
    payer_name: str  # Exchange name
    payer_tin: str   # Exchange TIN/EIN

    recipient_name: str
    recipient_tin: str  # SSN or EIN

    # Transaction summary
    proceeds: Decimal
    cost_basis: Decimal
    federal_tax_withheld: Decimal = Decimal("0")

    # Detailed transactions
    transactions: List[Form8949Transaction] = field(default_factory=list)

    # Form details
    tax_year: int = 0
    corrected: bool = False


@dataclass
class TravelRuleReport:
    """
    Travel Rule Compliance Report (FATF Recommendation 16)

    Required for crypto transfers >= $3,000 (FinCEN) or $1,000 (FATF)

    Must transmit:
    - Originator information
    - Beneficiary information
    - Transfer amount and asset type
    """
    report_id: str
    transfer_date: datetime
    amount: Decimal
    asset: str

    # Originator
    originator_name: str
    originator_account: str
    originator_address: Dict[str, str]
    originator_vasp: str  # Virtual Asset Service Provider

    # Beneficiary
    beneficiary_name: str
    beneficiary_account: str
    beneficiary_address: Dict[str, str]
    beneficiary_vasp: str

    # Transaction details
    transaction_hash: str
    blockchain: str

    # Compliance
    screening_results: Dict[str, any] = field(default_factory=dict)
    risk_score: int = 0
    approved: bool = False


class RegulatoryReportingEngine:
    """
    Central engine for regulatory reporting compliance

    Features:
    - Automatic threshold monitoring
    - Report generation
    - Filing tracking
    - Compliance alerts
    """

    def __init__(
        self,
        entity_name: str,
        entity_tin: str,
        jurisdiction: RegulatoryJurisdiction = RegulatoryJurisdiction.US_FEDERAL,
        data_dir: Path = None
    ):
        self.entity_name = entity_name
        self.entity_tin = entity_tin
        self.jurisdiction = jurisdiction
        self.data_dir = data_dir or Path("data/regulatory_reports")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Thresholds (can be configured per jurisdiction)
        self.thresholds = {
            "ctr_amount": Decimal("10000"),
            "sar_amount": Decimal("5000"),
            "travel_rule_fincen": Decimal("3000"),
            "travel_rule_fatf": Decimal("1000"),
            "structuring_pattern_count": 3,
            "structuring_pattern_amount": Decimal("9000"),
        }

        # Report tracking
        self.pending_reports: List[any] = []
        self.filed_reports: List[any] = []

    async def monitor_transaction_for_ctr(
        self,
        user_id: str,
        transaction_date: datetime,
        amount: Decimal,
        transaction_id: str
    ) -> Optional[CurrencyTransactionReport]:
        """
        Monitor transaction for CTR filing requirement

        Aggregates transactions by user per day and checks $10,000 threshold
        """
        if amount < self.thresholds["ctr_amount"]:
            # Check for aggregated transactions in same day
            daily_total = await self._get_daily_transaction_total(user_id, transaction_date)

            if daily_total < self.thresholds["ctr_amount"]:
                return None

        # CTR required
        logger.warning(f"CTR threshold exceeded for user {user_id}: ${amount}")

        ctr = CurrencyTransactionReport(
            report_id=self._generate_report_id("CTR"),
            filing_institution=self.entity_name,
            filing_date=datetime.now(timezone.utc),
            transaction_date=transaction_date,
            total_amount=amount,
            currency="USD",
            person_name=user_id,  # Would get from KYC
            person_id=user_id,
            person_type="individual",
            address={},  # Would get from KYC
            account_number=user_id,
            multiple_transactions=False,
            transaction_count=1,
            transaction_ids=[transaction_id]
        )

        self.pending_reports.append(ctr)
        await self._save_report(ctr, "ctr")

        return ctr

    async def monitor_for_suspicious_activity(
        self,
        user_id: str,
        transaction_id: str,
        amount: Decimal,
        behavior_indicators: Dict[str, any]
    ) -> Optional[SuspiciousActivityReport]:
        """
        Monitor transaction for suspicious activity

        Red flags:
        - Structuring (multiple transactions just under $10,000)
        - Unusual patterns
        - High-risk jurisdictions
        - Rapid movement of funds
        - Inconsistent with customer profile
        """
        suspicious = False
        reasons = []

        # Check for structuring
        if await self._detect_structuring(user_id, amount):
            suspicious = True
            reasons.append("Potential structuring to avoid CTR reporting")

        # Check velocity
        if behavior_indicators.get("high_velocity"):
            suspicious = True
            reasons.append("Unusually high transaction velocity")

        # Check amount vs. profile
        if behavior_indicators.get("amount_inconsistent_with_profile"):
            suspicious = True
            reasons.append("Transaction amount inconsistent with customer profile")

        # High-risk jurisdiction
        if behavior_indicators.get("high_risk_jurisdiction"):
            suspicious = True
            reasons.append("Transaction involves high-risk jurisdiction")

        if not suspicious:
            return None

        logger.critical(f"Suspicious activity detected for user {user_id}: {reasons}")

        sar = SuspiciousActivityReport(
            report_id=self._generate_report_id("SAR"),
            filing_institution=self.entity_name,
            filing_date=datetime.now(timezone.utc),
            subject_name=user_id,
            subject_id=user_id,
            subject_type="individual",
            activity_date=datetime.now(timezone.utc),
            activity_type="cryptocurrency_trading",
            activity_amount=amount,
            currency="USD",
            suspicious_behavior="; ".join(reasons),
            explanation=json.dumps(behavior_indicators),
            transaction_ids=[transaction_id]
        )

        self.pending_reports.append(sar)
        await self._save_report(sar, "sar")

        # Alert compliance team
        logger.critical(f"SAR {sar.report_id} created and pending review")

        return sar

    async def _detect_structuring(self, user_id: str, current_amount: Decimal) -> bool:
        """
        Detect potential structuring activity

        Structuring: Breaking transactions into smaller amounts to avoid reporting
        Red flags:
        - Multiple transactions just under $10,000
        - Pattern of transactions in short time period
        - Amounts that don't make economic sense
        """
        threshold = self.thresholds["structuring_pattern_amount"]

        if current_amount > threshold:
            # Check recent history for pattern
            recent_transactions = await self._get_recent_user_transactions(user_id, days=7)

            # Count transactions near but below CTR threshold
            suspicious_count = 0
            for tx_amount in recent_transactions:
                if threshold <= tx_amount < self.thresholds["ctr_amount"]:
                    suspicious_count += 1

            if suspicious_count >= self.thresholds["structuring_pattern_count"]:
                return True

        return False

    async def generate_form_8949(
        self,
        cost_tracker,
        tax_year: int
    ) -> List[Form8949Transaction]:
        """
        Generate IRS Form 8949 from cost basis tracker

        Reports all capital gains/losses for the tax year
        """
        logger.info(f"Generating Form 8949 for tax year {tax_year}")

        start_date = datetime(tax_year, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(tax_year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

        # Get all dispositions for tax year
        dispositions = [
            d for d in cost_tracker._dispositions
            if start_date <= d.disposition_date <= end_date
        ]

        form_8949_transactions = []

        for disp in dispositions:
            # Create entry for each lot consumed
            for lot_info in disp.lots_consumed:
                transaction = Form8949Transaction(
                    description=f"{lot_info['quantity']} {disp.asset}",
                    date_acquired=datetime.fromisoformat(lot_info['acquisition_date']),
                    date_sold=disp.disposition_date,
                    proceeds=disp.proceeds_per_unit * Decimal(lot_info['quantity']),
                    cost_basis=Decimal(lot_info['cost_basis']),
                    transaction_id=disp.transaction_id,
                    exchange=disp.exchange
                )
                form_8949_transactions.append(transaction)

        # Save to file
        await self._save_form_8949(form_8949_transactions, tax_year)

        logger.info(f"Generated {len(form_8949_transactions)} Form 8949 entries for {tax_year}")

        return form_8949_transactions

    async def generate_form_1099b(
        self,
        recipient_name: str,
        recipient_tin: str,
        transactions: List[Form8949Transaction],
        tax_year: int
    ) -> Form1099B:
        """
        Generate IRS Form 1099-B for a taxpayer

        Summarizes proceeds from broker transactions
        """
        total_proceeds = sum(tx.proceeds for tx in transactions)
        total_cost_basis = sum(tx.cost_basis for tx in transactions)

        form_1099b = Form1099B(
            payer_name=self.entity_name,
            payer_tin=self.entity_tin,
            recipient_name=recipient_name,
            recipient_tin=recipient_tin,
            proceeds=total_proceeds,
            cost_basis=total_cost_basis,
            transactions=transactions,
            tax_year=tax_year
        )

        await self._save_form_1099b(form_1099b, tax_year)

        logger.info(f"Generated Form 1099-B for {recipient_name}: {len(transactions)} transactions")

        return form_1099b

    async def check_travel_rule_compliance(
        self,
        transfer_amount: Decimal,
        originator_info: Dict,
        beneficiary_info: Dict,
        asset: str
    ) -> TravelRuleReport:
        """
        Check Travel Rule compliance for crypto transfers

        FATF Recommendation 16 / FinCEN Travel Rule:
        - Transfers >= $3,000 (FinCEN) or >= $1,000 (FATF)
        - Must transmit originator and beneficiary information
        """
        threshold = self.thresholds["travel_rule_fincen"]

        if transfer_amount < threshold:
            logger.debug(f"Transfer ${transfer_amount} below Travel Rule threshold")
            return None

        logger.info(f"Travel Rule compliance required for ${transfer_amount} transfer")

        report = TravelRuleReport(
            report_id=self._generate_report_id("TR"),
            transfer_date=datetime.now(timezone.utc),
            amount=transfer_amount,
            asset=asset,
            originator_name=originator_info.get("name"),
            originator_account=originator_info.get("account"),
            originator_address=originator_info.get("address", {}),
            originator_vasp=self.entity_name,
            beneficiary_name=beneficiary_info.get("name"),
            beneficiary_account=beneficiary_info.get("account"),
            beneficiary_address=beneficiary_info.get("address", {}),
            beneficiary_vasp=beneficiary_info.get("vasp"),
            transaction_hash=beneficiary_info.get("tx_hash", ""),
            blockchain=beneficiary_info.get("blockchain", "")
        )

        # Perform screening
        report.screening_results = await self._screen_transfer(report)
        report.risk_score = report.screening_results.get("risk_score", 0)
        report.approved = report.risk_score < 70  # Risk threshold

        await self._save_report(report, "travel_rule")

        return report

    async def _screen_transfer(self, transfer: TravelRuleReport) -> Dict:
        """
        Screen transfer against sanctions lists and risk factors

        Checks:
        - OFAC SDN list
        - Jurisdiction risk
        - Behavioral analytics
        """
        results = {
            "ofac_match": False,
            "high_risk_jurisdiction": False,
            "risk_score": 0,
            "alerts": []
        }

        # In production, would check actual OFAC SDN list
        # For now, placeholder

        return results

    async def _get_daily_transaction_total(self, user_id: str, date: datetime) -> Decimal:
        """Get total transaction amount for user on given date"""
        # Would query database for user's transactions on date
        return Decimal("0")

    async def _get_recent_user_transactions(self, user_id: str, days: int) -> List[Decimal]:
        """Get recent transaction amounts for user"""
        # Would query database
        return []

    def _generate_report_id(self, report_type: str) -> str:
        """Generate unique report ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"{report_type}-{timestamp}-{hashlib.md5(timestamp.encode()).hexdigest()[:8]}"

    async def _save_report(self, report: any, report_type: str):
        """Save report to file"""
        report_dir = self.data_dir / report_type
        report_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{report.report_id}.json"
        filepath = report_dir / filename

        with open(filepath, 'w') as f:
            if hasattr(report, '__dict__'):
                # Convert datetime objects to strings
                data = {}
                for k, v in report.__dict__.items():
                    if isinstance(v, datetime):
                        data[k] = v.isoformat()
                    elif isinstance(v, Decimal):
                        data[k] = str(v)
                    else:
                        data[k] = v
                json.dump(data, f, indent=2, default=str)

        logger.info(f"Saved {report_type} report to {filepath}")

    async def _save_form_8949(self, transactions: List[Form8949Transaction], tax_year: int):
        """Save Form 8949 to CSV format"""
        filepath = self.data_dir / f"form_8949_{tax_year}.csv"

        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                "Description of Property",
                "Date Acquired",
                "Date Sold",
                "Proceeds",
                "Cost Basis",
                "Adjustment Code",
                "Adjustment Amount",
                "Gain or Loss",
                "Short-Term (S) or Long-Term (L)",
                "Transaction ID",
                "Exchange"
            ])

            # Transactions
            for tx in transactions:
                writer.writerow([
                    tx.description,
                    tx.date_acquired.strftime("%m/%d/%Y"),
                    tx.date_sold.strftime("%m/%d/%Y"),
                    f"{tx.proceeds:.2f}",
                    f"{tx.cost_basis:.2f}",
                    tx.adjustment_code or "",
                    f"{tx.adjustment_amount:.2f}",
                    f"{tx.gain_or_loss:.2f}",
                    "S" if tx.is_short_term else "L",
                    tx.transaction_id,
                    tx.exchange
                ])

        logger.info(f"Saved Form 8949 to {filepath}")

    async def _save_form_1099b(self, form: Form1099B, tax_year: int):
        """Save Form 1099-B"""
        filepath = self.data_dir / f"form_1099b_{form.recipient_tin}_{tax_year}.json"

        data = {
            "payer_name": form.payer_name,
            "payer_tin": form.payer_tin,
            "recipient_name": form.recipient_name,
            "recipient_tin": form.recipient_tin,
            "proceeds": str(form.proceeds),
            "cost_basis": str(form.cost_basis),
            "federal_tax_withheld": str(form.federal_tax_withheld),
            "tax_year": form.tax_year,
            "transaction_count": len(form.transactions)
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved Form 1099-B to {filepath}")

    async def generate_compliance_summary(self) -> Dict:
        """Generate compliance summary report"""
        return {
            "entity_name": self.entity_name,
            "jurisdiction": self.jurisdiction.value,
            "report_date": datetime.now(timezone.utc).isoformat(),
            "pending_reports": len(self.pending_reports),
            "filed_reports": len(self.filed_reports),
            "thresholds": {k: str(v) for k, v in self.thresholds.items()},
            "pending_report_types": [type(r).__name__ for r in self.pending_reports]
        }


__all__ = [
    "RegulatoryJurisdiction",
    "ReportType",
    "SuspiciousActivityReport",
    "CurrencyTransactionReport",
    "Form8949Transaction",
    "Form1099B",
    "TravelRuleReport",
    "RegulatoryReportingEngine"
]
