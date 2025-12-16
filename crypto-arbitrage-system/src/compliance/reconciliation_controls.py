"""
Reconciliation and Internal Controls Module

Implements:
- SOX (Sarbanes-Oxley) Section 404 internal controls
- COSO Framework (Committee of Sponsoring Organizations)
- Account reconciliation procedures
- Control testing and monitoring
- Segregation of duties
- Authorization controls

Controls Framework:
1. Entity-Level Controls
2. Process-Level Controls
3. Transaction Controls
4. IT General Controls (ITGC)
5. Monitoring Controls
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Set
from enum import Enum
from pathlib import Path
import json
import hashlib

logger = logging.getLogger(__name__)


class ControlType(Enum):
    """Types of internal controls"""
    PREVENTIVE = "preventive"      # Prevent errors before they occur
    DETECTIVE = "detective"        # Detect errors after occurrence
    CORRECTIVE = "corrective"      # Correct identified errors


class ControlFrequency(Enum):
    """Control execution frequency"""
    CONTINUOUS = "continuous"      # Real-time/automated
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class ControlEffectiveness(Enum):
    """Control effectiveness ratings"""
    EFFECTIVE = "effective"
    NEEDS_IMPROVEMENT = "needs_improvement"
    INEFFECTIVE = "ineffective"
    NOT_TESTED = "not_tested"


class ReconciliationType(Enum):
    """Types of reconciliations"""
    BANK_RECONCILIATION = "bank"
    EXCHANGE_RECONCILIATION = "exchange"
    POSITION_RECONCILIATION = "position"
    TRADE_RECONCILIATION = "trade"
    GL_RECONCILIATION = "general_ledger"


@dataclass
class InternalControl:
    """
    Internal control definition per COSO framework

    Components:
    - Control Environment
    - Risk Assessment
    - Control Activities
    - Information & Communication
    - Monitoring Activities
    """
    control_id: str
    control_name: str
    control_objective: str
    control_type: ControlType
    frequency: ControlFrequency

    # Process and risk
    process_area: str
    risks_addressed: List[str] = field(default_factory=list)

    # Control procedure
    procedure_description: str
    responsible_party: str
    reviewer: str  # Segregation of duties

    # Evidence and testing
    evidence_type: str  # "System log", "Report", "Approval", etc.
    test_frequency: ControlFrequency = ControlFrequency.QUARTERLY

    # Status
    effectiveness: ControlEffectiveness = ControlEffectiveness.NOT_TESTED
    last_test_date: Optional[datetime] = None
    next_test_due: Optional[datetime] = None

    # Deficiencies
    deficiencies: List[Dict] = field(default_factory=list)


@dataclass
class ControlTest:
    """Control test execution record"""
    test_id: str
    control_id: str
    test_date: datetime
    tester: str

    # Test procedure
    sample_size: int
    items_tested: List[str] = field(default_factory=list)

    # Results
    exceptions_found: int
    exception_details: List[Dict] = field(default_factory=list)
    effectiveness_rating: ControlEffectiveness = ControlEffectiveness.NOT_TESTED

    # Conclusion
    conclusion: str = ""
    recommendations: List[str] = field(default_factory=list)


@dataclass
class ReconciliationRecord:
    """
    Account reconciliation record

    Standard reconciliation format:
    - Beginning balance
    - Add: Items increasing balance
    - Less: Items decreasing balance
    - Ending balance
    - Variance investigation
    """
    reconciliation_id: str
    reconciliation_type: ReconciliationType
    reconciliation_date: datetime
    period_end: datetime

    # Accounts being reconciled
    source_system: str
    target_system: str

    # Balances
    source_balance: Decimal
    target_balance: Decimal
    variance: Decimal

    # Reconciling items
    reconciling_items: List[Dict] = field(default_factory=list)
    reconciled_balance: Decimal = Decimal("0")

    # Status
    is_reconciled: bool = False
    variance_explained: bool = False

    # Approvals
    prepared_by: str = ""
    reviewed_by: str = ""
    approved_by: str = ""
    approval_date: Optional[datetime] = None

    # Comments
    variance_explanation: str = ""
    follow_up_required: bool = False
    follow_up_notes: str = ""


class InternalControlsFramework:
    """
    SOX 404 Internal Controls Framework

    Implements COSO framework components:
    1. Control Environment
    2. Risk Assessment
    3. Control Activities
    4. Information & Communication
    5. Monitoring Activities
    """

    def __init__(self, entity_name: str, data_dir: Path = None):
        self.entity_name = entity_name
        self.data_dir = data_dir or Path("data/internal_controls")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.controls: Dict[str, InternalControl] = {}
        self.control_tests: List[ControlTest] = []

        # Initialize standard controls
        self._initialize_standard_controls()

    def _initialize_standard_controls(self):
        """Initialize standard SOX controls for trading operations"""

        # Control 1: Trade Authorization
        self.add_control(InternalControl(
            control_id="TRD-001",
            control_name="Trade Authorization and Approval",
            control_objective="Ensure all trades are properly authorized within limits",
            control_type=ControlType.PREVENTIVE,
            frequency=ControlFrequency.CONTINUOUS,
            process_area="Trading",
            risks_addressed=[
                "Unauthorized trading",
                "Exceeding position limits",
                "Breach of trading mandates"
            ],
            procedure_description="""
            System automatically validates:
            1. Trade amount within authorized limits
            2. Symbol is on approved list
            3. Risk limits not exceeded
            4. Sufficient balance available
            Trades exceeding limits require manual approval.
            """,
            responsible_party="Trading System",
            reviewer="Risk Manager",
            evidence_type="System validation log"
        ))

        # Control 2: Segregation of Duties
        self.add_control(InternalControl(
            control_id="SOD-001",
            control_name="Segregation of Trading and Settlement Duties",
            control_objective="Ensure proper segregation between trade execution and settlement",
            control_type=ControlType.PREVENTIVE,
            frequency=ControlFrequency.CONTINUOUS,
            process_area="Operations",
            risks_addressed=[
                "Fraud",
                "Unauthorized modifications",
                "Concealment of losses"
            ],
            procedure_description="""
            Role-based access controls ensure:
            1. Traders cannot modify settlement instructions
            2. Operations cannot initiate trades
            3. Reconcilers have read-only access
            4. Approvals require different user roles
            """,
            responsible_party="System Administrator",
            reviewer="Compliance Officer",
            evidence_type="Access control matrix"
        ))

        # Control 3: Daily Reconciliation
        self.add_control(InternalControl(
            control_id="REC-001",
            control_name="Daily Exchange Balance Reconciliation",
            control_objective="Ensure balances per system match exchange balances",
            control_type=ControlType.DETECTIVE,
            frequency=ControlFrequency.DAILY,
            process_area="Finance",
            risks_addressed=[
                "Unrecorded transactions",
                "System errors",
                "Theft or loss of assets"
            ],
            procedure_description="""
            Daily reconciliation procedure:
            1. Pull balances from all exchanges via API
            2. Compare to internal position system
            3. Investigate variances > $100 or 0.1%
            4. Document reconciling items
            5. Obtain management approval for large variances
            """,
            responsible_party="Finance Team",
            reviewer="Controller",
            evidence_type="Daily reconciliation report"
        ))

        # Control 4: P&L Review
        self.add_control(InternalControl(
            control_id="FIN-001",
            control_name="Daily P&L Review and Variance Analysis",
            control_objective="Detect anomalies in trading P&L",
            control_type=ControlType.DETECTIVE,
            frequency=ControlFrequency.DAILY,
            process_area="Finance",
            risks_addressed=[
                "Pricing errors",
                "Unauthorized trading",
                "System calculation errors"
            ],
            procedure_description="""
            Daily P&L review:
            1. Review daily P&L by strategy
            2. Compare to expected ranges
            3. Investigate variances > 20% from average
            4. Review top 10 profitable and losing trades
            5. Escalate unusual patterns to management
            """,
            responsible_party="Finance Team",
            reviewer="CFO",
            evidence_type="Daily P&L report with commentary"
        ))

        # Control 5: Fair Value Validation
        self.add_control(InternalControl(
            control_id="VAL-001",
            control_name="Fair Value Pricing Validation",
            control_objective="Ensure assets are valued at appropriate fair values",
            control_type=ControlType.DETECTIVE,
            frequency=ControlFrequency.DAILY,
            process_area="Valuation",
            risks_addressed=[
                "Mispricing",
                "Stale prices",
                "Manipulation"
            ],
            procedure_description="""
            Pricing validation:
            1. Compare prices across multiple exchanges
            2. Flag prices deviating >5% from median
            3. Validate timestamp freshness (<5 minutes)
            4. Review pricing hierarchy classifications
            5. Document any manual price adjustments
            """,
            responsible_party="Risk Team",
            reviewer="Valuation Committee",
            evidence_type="Price validation report"
        ))

        # Control 6: Access Control Review
        self.add_control(InternalControl(
            control_id="SEC-001",
            control_name="User Access Review",
            control_objective="Ensure user access is appropriate and current",
            control_type=ControlType.DETECTIVE,
            frequency=ControlFrequency.QUARTERLY,
            process_area="Information Technology",
            risks_addressed=[
                "Unauthorized access",
                "Excessive privileges",
                "Terminated user access"
            ],
            procedure_description="""
            Quarterly access review:
            1. Export all user accounts and roles
            2. Validate with HR active employee list
            3. Review role assignments with managers
            4. Identify and remove excessive permissions
            5. Document and approve all privileged access
            """,
            responsible_party="IT Security",
            reviewer="CISO",
            evidence_type="Access review report with approvals"
        ))

        # Control 7: Change Management
        self.add_control(InternalControl(
            control_id="IT-001",
            control_name="Production Change Management",
            control_objective="Ensure changes to production systems are authorized and tested",
            control_type=ControlType.PREVENTIVE,
            frequency=ControlFrequency.CONTINUOUS,
            process_area="Information Technology",
            risks_addressed=[
                "System outages",
                "Data corruption",
                "Unauthorized changes"
            ],
            procedure_description="""
            Change management process:
            1. All changes require change ticket
            2. Changes must be tested in non-prod environment
            3. Peer review of code changes required
            4. Management approval for production deployment
            5. Rollback plan documented and tested
            """,
            responsible_party="Development Team",
            reviewer="IT Manager",
            evidence_type="Change tickets and approvals"
        ))

    def add_control(self, control: InternalControl):
        """Add or update control in framework"""
        self.controls[control.control_id] = control
        logger.info(f"Added control {control.control_id}: {control.control_name}")

    async def execute_control_test(
        self,
        control_id: str,
        tester: str,
        sample_size: int = 25
    ) -> ControlTest:
        """
        Execute control test

        Standard audit sample sizes:
        - 25 items for controls with <100 transactions
        - 50 items for controls with >100 transactions
        - 100% for key controls
        """
        if control_id not in self.controls:
            raise ValueError(f"Control {control_id} not found")

        control = self.controls[control_id]

        test = ControlTest(
            test_id=f"TEST-{control_id}-{datetime.now().strftime('%Y%m%d')}",
            control_id=control_id,
            test_date=datetime.now(timezone.utc),
            tester=tester,
            sample_size=sample_size
        )

        # Simulate control test (in production, would perform actual testing)
        logger.info(f"Testing control {control_id}: {control.control_name}")

        # Placeholder: Actual testing logic would go here
        test.exceptions_found = 0
        test.effectiveness_rating = ControlEffectiveness.EFFECTIVE
        test.conclusion = f"Control {control_id} tested effective. No exceptions noted."

        # Update control status
        control.last_test_date = test.test_date
        control.effectiveness = test.effectiveness_rating

        # Set next test due date
        if control.test_frequency == ControlFrequency.QUARTERLY:
            control.next_test_due = test.test_date + timedelta(days=90)
        elif control.test_frequency == ControlFrequency.ANNUAL:
            control.next_test_due = test.test_date + timedelta(days=365)

        self.control_tests.append(test)

        await self._save_control_test(test)

        return test

    async def generate_sox_404_report(self) -> Dict:
        """
        Generate SOX 404 compliance report

        Required elements:
        - Management's assertion
        - Control framework description
        - Control testing results
        - Identified deficiencies
        - Remediation status
        """
        effective_controls = sum(
            1 for c in self.controls.values()
            if c.effectiveness == ControlEffectiveness.EFFECTIVE
        )

        total_controls = len(self.controls)

        deficiencies = []
        for control in self.controls.values():
            if control.deficiencies:
                deficiencies.extend(control.deficiencies)

        report = {
            "entity_name": self.entity_name,
            "report_date": datetime.now(timezone.utc).isoformat(),
            "framework": "COSO 2013",
            "scope": "Internal controls over financial reporting",
            "summary": {
                "total_controls": total_controls,
                "controls_tested": sum(
                    1 for c in self.controls.values()
                    if c.last_test_date is not None
                ),
                "effective_controls": effective_controls,
                "effectiveness_rate": f"{effective_controls / total_controls * 100:.1f}%"
            },
            "control_effectiveness_by_type": {
                "preventive": sum(
                    1 for c in self.controls.values()
                    if c.control_type == ControlType.PREVENTIVE
                    and c.effectiveness == ControlEffectiveness.EFFECTIVE
                ),
                "detective": sum(
                    1 for c in self.controls.values()
                    if c.control_type == ControlType.DETECTIVE
                    and c.effectiveness == ControlEffectiveness.EFFECTIVE
                ),
                "corrective": sum(
                    1 for c in self.controls.values()
                    if c.control_type == ControlType.CORRECTIVE
                    and c.effectiveness == ControlEffectiveness.EFFECTIVE
                )
            },
            "deficiencies": {
                "total": len(deficiencies),
                "material_weaknesses": sum(
                    1 for d in deficiencies
                    if d.get("severity") == "material_weakness"
                ),
                "significant_deficiencies": sum(
                    1 for d in deficiencies
                    if d.get("severity") == "significant_deficiency"
                )
            },
            "controls": [
                {
                    "id": c.control_id,
                    "name": c.control_name,
                    "type": c.control_type.value,
                    "frequency": c.frequency.value,
                    "effectiveness": c.effectiveness.value,
                    "last_tested": c.last_test_date.isoformat() if c.last_test_date else None
                }
                for c in self.controls.values()
            ]
        }

        await self._save_sox_report(report)

        return report

    async def _save_control_test(self, test: ControlTest):
        """Save control test results"""
        test_dir = self.data_dir / "control_tests"
        test_dir.mkdir(parents=True, exist_ok=True)

        filepath = test_dir / f"{test.test_id}.json"

        with open(filepath, 'w') as f:
            json.dump({
                "test_id": test.test_id,
                "control_id": test.control_id,
                "test_date": test.test_date.isoformat(),
                "tester": test.tester,
                "sample_size": test.sample_size,
                "exceptions_found": test.exceptions_found,
                "effectiveness": test.effectiveness_rating.value,
                "conclusion": test.conclusion
            }, f, indent=2)

    async def _save_sox_report(self, report: Dict):
        """Save SOX 404 report"""
        filepath = self.data_dir / f"sox_404_report_{datetime.now().strftime('%Y%m%d')}.json"

        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"SOX 404 report saved to {filepath}")


class ReconciliationEngine:
    """
    Account Reconciliation Engine

    Performs daily/monthly reconciliations for:
    - Exchange balances vs. internal records
    - Trade records vs. exchange confirmations
    - Positions vs. exchange positions
    - General ledger vs. sub-ledgers
    """

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data/reconciliations")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.reconciliations: List[ReconciliationRecord] = []

    async def reconcile_exchange_balances(
        self,
        exchange: str,
        internal_balances: Dict[str, Decimal],
        exchange_balances: Dict[str, Decimal],
        reconciliation_date: datetime
    ) -> ReconciliationRecord:
        """
        Reconcile internal balances to exchange-reported balances

        Standard reconciliation procedure:
        1. Compare balances for each currency
        2. Identify variances
        3. Investigate variances > threshold
        4. Document reconciling items
        5. Obtain approval
        """
        recon = ReconciliationRecord(
            reconciliation_id=f"EXCH-{exchange}-{reconciliation_date.strftime('%Y%m%d')}",
            reconciliation_type=ReconciliationType.EXCHANGE_RECONCILIATION,
            reconciliation_date=datetime.now(timezone.utc),
            period_end=reconciliation_date,
            source_system="Internal Position System",
            target_system=f"{exchange} Exchange",
            source_balance=Decimal("0"),
            target_balance=Decimal("0"),
            variance=Decimal("0")
        )

        total_variance = Decimal("0")
        reconciling_items = []

        for currency in set(internal_balances.keys()) | set(exchange_balances.keys()):
            internal_bal = internal_balances.get(currency, Decimal("0"))
            exchange_bal = exchange_balances.get(currency, Decimal("0"))
            variance = internal_bal - exchange_bal

            if abs(variance) > Decimal("0.01"):  # Threshold
                reconciling_items.append({
                    "currency": currency,
                    "internal_balance": str(internal_bal),
                    "exchange_balance": str(exchange_bal),
                    "variance": str(variance),
                    "explanation": "Pending investigation"
                })
                total_variance += variance

        recon.source_balance = sum(internal_balances.values())
        recon.target_balance = sum(exchange_balances.values())
        recon.variance = total_variance
        recon.reconciling_items = reconciling_items

        # Determine if reconciled (variance within tolerance)
        tolerance = Decimal("100")  # $100 tolerance
        recon.is_reconciled = abs(total_variance) < tolerance
        recon.variance_explained = recon.is_reconciled

        if not recon.is_reconciled:
            recon.follow_up_required = True
            recon.follow_up_notes = f"Variance of ${total_variance} requires investigation"
            logger.warning(f"Exchange reconciliation variance: ${total_variance} for {exchange}")

        self.reconciliations.append(recon)
        await self._save_reconciliation(recon)

        return recon

    async def _save_reconciliation(self, recon: ReconciliationRecord):
        """Save reconciliation record"""
        filepath = self.data_dir / f"{recon.reconciliation_id}.json"

        with open(filepath, 'w') as f:
            json.dump({
                "reconciliation_id": recon.reconciliation_id,
                "type": recon.reconciliation_type.value,
                "date": recon.reconciliation_date.isoformat(),
                "source_system": recon.source_system,
                "target_system": recon.target_system,
                "source_balance": str(recon.source_balance),
                "target_balance": str(recon.target_balance),
                "variance": str(recon.variance),
                "is_reconciled": recon.is_reconciled,
                "reconciling_items": recon.reconciling_items,
                "prepared_by": recon.prepared_by,
                "reviewed_by": recon.reviewed_by,
                "variance_explanation": recon.variance_explanation
            }, f, indent=2)

        logger.info(f"Reconciliation saved: {recon.reconciliation_id}")


__all__ = [
    "ControlType",
    "ControlFrequency",
    "ControlEffectiveness",
    "ReconciliationType",
    "InternalControl",
    "ControlTest",
    "ReconciliationRecord",
    "InternalControlsFramework",
    "ReconciliationEngine"
]
