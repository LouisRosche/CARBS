"""
Compliance and Accounting Module

Provides comprehensive GAAP and regulatory compliance:

GAAP Financial Reporting:
- Complete financial statements (Balance Sheet, Income Statement, Cash Flow)
- GAAP-compliant trade journaling
- Revenue recognition per ASC 606
- Fair value measurement per ASC 820
- Notes to financial statements

Tax Compliance:
- Tax lot tracking (FIFO, LIFO, HIFO, specific identification)
- Form 8949 generation (capital gains/losses)
- Form 1099-B generation
- Cost basis reconciliation
- Multi-jurisdiction support
- Missouri state tax reporting (capital gains exemption as of Aug 28, 2025)

Regulatory Reporting:
- FinCEN compliance (CTR, SAR, Travel Rule)
- IRS reporting (8949, 1099-B)
- SEC reporting framework (10-K, 10-Q, 8-K ready)
- Anti-money laundering (AML) monitoring
- Know Your Customer (KYC) integration

Internal Controls:
- SOX 404 compliance framework
- COSO internal controls
- Account reconciliation procedures
- Control testing and monitoring
- Segregation of duties enforcement

Data Privacy:
- GDPR compliance (data deletion, export)
- SOC2 audit trail features
- Data retention policy enforcement

Data Export:
- Accountant-friendly formats (CSV, JSON)
- Tax software compatibility
- Audit package generation

Module Structure:
- enums.py: CostBasisMethod, AssetClass, TaxJurisdiction
- models.py: TaxLot, DispositionRecord, TradeJournalEntry
- cost_basis.py: CostBasisTracker
- journal.py: TradeJournal
- exporter.py: DataExporter
- missouri_tax.py: MissouriTaxCalculator, MissouriFormGenerator, export_missouri_tax_package
- form_1099_da.py: Form1099DA, Form1099DAReconciler, ReconciliationReport (for 2026+ tax years)
- gdpr.py: GDPRCompliance
- soc2.py: SOC2Controls
"""

from pathlib import Path

# Import from submodules for backward compatibility
from .enums import CostBasisMethod, AssetClass, TaxJurisdiction
from .models import TaxLot, DispositionRecord, TradeJournalEntry
from .cost_basis import CostBasisTracker
from .journal import TradeJournal
from .exporter import DataExporter
from .missouri_tax import MissouriTaxCalculator, MissouriFormGenerator, export_missouri_tax_package
from .form_1099_da import Form1099DA, Form1099DAReconciler, ReconciliationReport, ReconciliationDiscrepancy
from .gdpr import GDPRCompliance
from .soc2 import SOC2Controls
from .manager import ComplianceManager


def create_compliance_suite(data_dir: Path = None) -> dict:
    """
    Create complete compliance suite

    Returns dict with all compliance components.
    """
    data_dir = data_dir or Path("data/compliance")
    data_dir.mkdir(parents=True, exist_ok=True)

    return {
        "cost_tracker": CostBasisTracker(data_dir=data_dir),
        "trade_journal": TradeJournal(data_dir=data_dir),
        "exporter": DataExporter(data_dir=data_dir / "exports"),
        "gdpr": GDPRCompliance(data_dir=data_dir),
        "soc2": SOC2Controls()
    }


__all__ = [
    # Enums
    "CostBasisMethod",
    "AssetClass",
    "TaxJurisdiction",

    # Models
    "TaxLot",
    "DispositionRecord",
    "TradeJournalEntry",
    "Form1099DA",
    "ReconciliationReport",
    "ReconciliationDiscrepancy",

    # Classes
    "CostBasisTracker",
    "TradeJournal",
    "DataExporter",
    "MissouriTaxCalculator",
    "MissouriFormGenerator",
    "Form1099DAReconciler",
    "GDPRCompliance",
    "SOC2Controls",

    # Orchestration
    "ComplianceManager",

    # Functions
    "create_compliance_suite",
    "export_missouri_tax_package",
]
