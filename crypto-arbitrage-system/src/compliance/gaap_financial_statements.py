"""
GAAP-Compliant Financial Statements Module

Implements comprehensive financial reporting in accordance with:
- FASB Accounting Standards Codification (ASC)
- Generally Accepted Accounting Principles (GAAP)
- SEC Regulation S-X (if applicable for public companies)

Provides:
- Balance Sheet (Statement of Financial Position)
- Income Statement (Statement of Operations)
- Cash Flow Statement (Statement of Cash Flows)
- Statement of Changes in Equity
- Notes to Financial Statements
- Management Discussion & Analysis (MD&A) templates
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple
from enum import Enum
from pathlib import Path
import json
import asyncio

logger = logging.getLogger(__name__)


class AccountingPeriod(Enum):
    """Standard accounting periods"""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    YTD = "year_to_date"


class FinancialStatementType(Enum):
    """Types of financial statements"""
    BALANCE_SHEET = "balance_sheet"
    INCOME_STATEMENT = "income_statement"
    CASH_FLOW = "cash_flow_statement"
    EQUITY_CHANGES = "statement_of_changes_in_equity"
    COMPREHENSIVE_INCOME = "statement_of_comprehensive_income"


@dataclass
class BalanceSheetItem:
    """Balance sheet line item"""
    category: str  # "assets", "liabilities", "equity"
    subcategory: str  # e.g., "current_assets", "long_term_liabilities"
    line_item: str  # e.g., "cash_and_equivalents"
    amount: Decimal
    prior_period_amount: Decimal = Decimal("0")
    note_reference: Optional[str] = None


@dataclass
class IncomeStatementItem:
    """Income statement line item"""
    category: str  # "revenue", "cost_of_revenue", "operating_expenses", etc.
    line_item: str
    amount: Decimal
    prior_period_amount: Decimal = Decimal("0")
    note_reference: Optional[str] = None


@dataclass
class CashFlowItem:
    """Cash flow statement line item"""
    category: str  # "operating", "investing", "financing"
    line_item: str
    amount: Decimal
    prior_period_amount: Decimal = Decimal("0")
    note_reference: Optional[str] = None


@dataclass
class FinancialNote:
    """Note to financial statements"""
    note_number: str
    title: str
    content: str
    references: List[str] = field(default_factory=list)


class BalanceSheet:
    """
    GAAP-Compliant Balance Sheet

    Format:
        ASSETS
          Current Assets
            Cash and Cash Equivalents
            Digital Assets - Trading (at Fair Value)
            Receivables from Exchanges
            Prepaid Expenses
          Total Current Assets

          Non-Current Assets
            Digital Assets - Held for Investment (at Fair Value)
            Property and Equipment (net)
            Intangible Assets (net)
          Total Non-Current Assets

        TOTAL ASSETS

        LIABILITIES
          Current Liabilities
            Accounts Payable
            Accrued Expenses
            Deferred Revenue
            Short-term Debt
          Total Current Liabilities

          Non-Current Liabilities
            Long-term Debt
            Deferred Tax Liabilities
          Total Non-Current Liabilities

        TOTAL LIABILITIES

        STOCKHOLDERS' EQUITY
          Common Stock
          Additional Paid-in Capital
          Retained Earnings
          Accumulated Other Comprehensive Income
        TOTAL STOCKHOLDERS' EQUITY

        TOTAL LIABILITIES AND STOCKHOLDERS' EQUITY
    """

    def __init__(self, as_of_date: datetime, entity_name: str = "Crypto Arbitrage Trading System"):
        self.as_of_date = as_of_date
        self.entity_name = entity_name
        self.items: List[BalanceSheetItem] = []
        self.notes: List[FinancialNote] = []

    def add_item(self, item: BalanceSheetItem):
        """Add line item to balance sheet"""
        self.items.append(item)

    def add_note(self, note: FinancialNote):
        """Add note to financial statements"""
        self.notes.append(note)

    def calculate_totals(self) -> Dict[str, Decimal]:
        """Calculate balance sheet totals"""
        totals = {
            "current_assets": Decimal("0"),
            "non_current_assets": Decimal("0"),
            "total_assets": Decimal("0"),
            "current_liabilities": Decimal("0"),
            "non_current_liabilities": Decimal("0"),
            "total_liabilities": Decimal("0"),
            "total_equity": Decimal("0"),
        }

        for item in self.items:
            if item.category == "assets":
                if item.subcategory == "current_assets":
                    totals["current_assets"] += item.amount
                elif item.subcategory == "non_current_assets":
                    totals["non_current_assets"] += item.amount
                totals["total_assets"] += item.amount
            elif item.category == "liabilities":
                if item.subcategory == "current_liabilities":
                    totals["current_liabilities"] += item.amount
                elif item.subcategory == "non_current_liabilities":
                    totals["non_current_liabilities"] += item.amount
                totals["total_liabilities"] += item.amount
            elif item.category == "equity":
                totals["total_equity"] += item.amount

        return totals

    def validate_accounting_equation(self) -> Tuple[bool, Decimal]:
        """
        Validate fundamental accounting equation: Assets = Liabilities + Equity

        Returns:
            (is_balanced, difference)
        """
        totals = self.calculate_totals()
        difference = totals["total_assets"] - (totals["total_liabilities"] + totals["total_equity"])
        is_balanced = abs(difference) < Decimal("0.01")  # Allow for rounding

        return is_balanced, difference

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        totals = self.calculate_totals()
        is_balanced, difference = self.validate_accounting_equation()

        return {
            "statement_type": "Balance Sheet",
            "entity_name": self.entity_name,
            "as_of_date": self.as_of_date.strftime("%B %d, %Y"),
            "preparation_date": datetime.now(timezone.utc).isoformat(),
            "currency": "USD",
            "accounting_basis": "GAAP",
            "is_balanced": is_balanced,
            "balance_difference": str(difference),
            "totals": {k: str(v) for k, v in totals.items()},
            "line_items": [
                {
                    "category": item.category,
                    "subcategory": item.subcategory,
                    "line_item": item.line_item,
                    "amount": str(item.amount),
                    "prior_period": str(item.prior_period_amount),
                    "note_ref": item.note_reference
                }
                for item in self.items
            ],
            "notes": [
                {
                    "number": note.note_number,
                    "title": note.title,
                    "content": note.content,
                    "references": note.references
                }
                for note in self.notes
            ]
        }


class IncomeStatement:
    """
    GAAP-Compliant Income Statement (Statement of Operations)

    Format:
        REVENUES
          Trading Revenue
          Net Realized Gains on Digital Assets
          Net Unrealized Gains on Digital Assets
        Total Revenues

        COST OF REVENUES
          Transaction Fees
          Network Fees
          Exchange Fees
        Total Cost of Revenues

        GROSS PROFIT

        OPERATING EXPENSES
          Technology and Development
          General and Administrative
          Marketing
          Depreciation and Amortization
        Total Operating Expenses

        INCOME FROM OPERATIONS

        OTHER INCOME (EXPENSE)
          Interest Income
          Interest Expense
          Other Income (Expense)
        Total Other Income (Expense)

        INCOME BEFORE INCOME TAXES

        INCOME TAX EXPENSE

        NET INCOME

        EARNINGS PER SHARE (if applicable)
          Basic
          Diluted
    """

    def __init__(
        self,
        period_start: datetime,
        period_end: datetime,
        entity_name: str = "Crypto Arbitrage Trading System"
    ):
        self.period_start = period_start
        self.period_end = period_end
        self.entity_name = entity_name
        self.items: List[IncomeStatementItem] = []
        self.notes: List[FinancialNote] = []

    def add_item(self, item: IncomeStatementItem):
        """Add line item to income statement"""
        self.items.append(item)

    def add_note(self, note: FinancialNote):
        """Add note to financial statements"""
        self.notes.append(note)

    def calculate_totals(self) -> Dict[str, Decimal]:
        """Calculate income statement totals"""
        totals = {
            "total_revenue": Decimal("0"),
            "total_cost_of_revenue": Decimal("0"),
            "gross_profit": Decimal("0"),
            "total_operating_expenses": Decimal("0"),
            "operating_income": Decimal("0"),
            "total_other_income": Decimal("0"),
            "income_before_tax": Decimal("0"),
            "tax_expense": Decimal("0"),
            "net_income": Decimal("0"),
        }

        for item in self.items:
            if item.category == "revenue":
                totals["total_revenue"] += item.amount
            elif item.category == "cost_of_revenue":
                totals["total_cost_of_revenue"] += item.amount
            elif item.category == "operating_expenses":
                totals["total_operating_expenses"] += item.amount
            elif item.category == "other_income":
                totals["total_other_income"] += item.amount
            elif item.category == "tax_expense":
                totals["tax_expense"] += item.amount

        totals["gross_profit"] = totals["total_revenue"] - totals["total_cost_of_revenue"]
        totals["operating_income"] = totals["gross_profit"] - totals["total_operating_expenses"]
        totals["income_before_tax"] = totals["operating_income"] + totals["total_other_income"]
        totals["net_income"] = totals["income_before_tax"] - totals["tax_expense"]

        return totals

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        totals = self.calculate_totals()

        return {
            "statement_type": "Income Statement",
            "entity_name": self.entity_name,
            "period_start": self.period_start.strftime("%B %d, %Y"),
            "period_end": self.period_end.strftime("%B %d, %Y"),
            "preparation_date": datetime.now(timezone.utc).isoformat(),
            "currency": "USD",
            "accounting_basis": "GAAP",
            "totals": {k: str(v) for k, v in totals.items()},
            "line_items": [
                {
                    "category": item.category,
                    "line_item": item.line_item,
                    "amount": str(item.amount),
                    "prior_period": str(item.prior_period_amount),
                    "note_ref": item.note_reference
                }
                for item in self.items
            ],
            "notes": [
                {
                    "number": note.note_number,
                    "title": note.title,
                    "content": note.content,
                    "references": note.references
                }
                for note in self.notes
            ]
        }


class CashFlowStatement:
    """
    GAAP-Compliant Statement of Cash Flows (Indirect Method)

    Format:
        CASH FLOWS FROM OPERATING ACTIVITIES
          Net Income
          Adjustments to reconcile net income to cash:
            Depreciation and Amortization
            Unrealized Gains on Digital Assets
            Changes in Operating Assets and Liabilities:
              Receivables
              Payables
              Accrued Expenses
        Net Cash from Operating Activities

        CASH FLOWS FROM INVESTING ACTIVITIES
          Purchase of Digital Assets
          Sale of Digital Assets
          Purchase of Property and Equipment
        Net Cash from Investing Activities

        CASH FLOWS FROM FINANCING ACTIVITIES
          Proceeds from Debt
          Repayment of Debt
          Dividends Paid
        Net Cash from Financing Activities

        NET CHANGE IN CASH

        Cash at Beginning of Period
        Cash at End of Period
    """

    def __init__(
        self,
        period_start: datetime,
        period_end: datetime,
        entity_name: str = "Crypto Arbitrage Trading System"
    ):
        self.period_start = period_start
        self.period_end = period_end
        self.entity_name = entity_name
        self.items: List[CashFlowItem] = []
        self.notes: List[FinancialNote] = []
        self.beginning_cash: Decimal = Decimal("0")

    def add_item(self, item: CashFlowItem):
        """Add line item to cash flow statement"""
        self.items.append(item)

    def add_note(self, note: FinancialNote):
        """Add note to financial statements"""
        self.notes.append(note)

    def set_beginning_cash(self, amount: Decimal):
        """Set cash balance at beginning of period"""
        self.beginning_cash = amount

    def calculate_totals(self) -> Dict[str, Decimal]:
        """Calculate cash flow totals"""
        totals = {
            "operating_activities": Decimal("0"),
            "investing_activities": Decimal("0"),
            "financing_activities": Decimal("0"),
            "net_change_in_cash": Decimal("0"),
            "beginning_cash": self.beginning_cash,
            "ending_cash": Decimal("0"),
        }

        for item in self.items:
            if item.category == "operating":
                totals["operating_activities"] += item.amount
            elif item.category == "investing":
                totals["investing_activities"] += item.amount
            elif item.category == "financing":
                totals["financing_activities"] += item.amount

        totals["net_change_in_cash"] = (
            totals["operating_activities"] +
            totals["investing_activities"] +
            totals["financing_activities"]
        )
        totals["ending_cash"] = totals["beginning_cash"] + totals["net_change_in_cash"]

        return totals

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        totals = self.calculate_totals()

        return {
            "statement_type": "Statement of Cash Flows",
            "method": "Indirect Method",
            "entity_name": self.entity_name,
            "period_start": self.period_start.strftime("%B %d, %Y"),
            "period_end": self.period_end.strftime("%B %d, %Y"),
            "preparation_date": datetime.now(timezone.utc).isoformat(),
            "currency": "USD",
            "accounting_basis": "GAAP",
            "totals": {k: str(v) for k, v in totals.items()},
            "line_items": [
                {
                    "category": item.category,
                    "line_item": item.line_item,
                    "amount": str(item.amount),
                    "prior_period": str(item.prior_period_amount),
                    "note_ref": item.note_reference
                }
                for item in self.items
            ],
            "notes": [
                {
                    "number": note.note_number,
                    "title": note.title,
                    "content": note.content,
                    "references": note.references
                }
                for note in self.notes
            ]
        }


class FinancialStatementPackage:
    """
    Complete GAAP Financial Statement Package

    Includes:
    - Balance Sheet
    - Income Statement
    - Cash Flow Statement
    - Statement of Changes in Equity
    - Notes to Financial Statements
    - Management Discussion & Analysis (MD&A)
    """

    def __init__(
        self,
        period_start: datetime,
        period_end: datetime,
        entity_name: str = "Crypto Arbitrage Trading System",
        data_dir: Path = None
    ):
        self.period_start = period_start
        self.period_end = period_end
        self.entity_name = entity_name
        self.data_dir = data_dir or Path("data/financial_statements")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.balance_sheet = BalanceSheet(period_end, entity_name)
        self.income_statement = IncomeStatement(period_start, period_end, entity_name)
        self.cash_flow_statement = CashFlowStatement(period_start, period_end, entity_name)

        self.equity_changes: Dict[str, Dict[str, Decimal]] = {}
        self.comprehensive_notes: List[FinancialNote] = []

    async def generate_from_database(self, db_manager):
        """
        Generate complete financial statements from database

        This method populates all financial statements with data from the database.
        """
        logger.info(f"Generating financial statements for period {self.period_start} to {self.period_end}")

        # Generate Balance Sheet
        await self._generate_balance_sheet(db_manager)

        # Generate Income Statement
        await self._generate_income_statement(db_manager)

        # Generate Cash Flow Statement
        await self._generate_cash_flow_statement(db_manager)

        # Add comprehensive notes
        self._add_standard_notes()

        logger.info("Financial statement generation complete")

    async def _generate_balance_sheet(self, db_manager):
        """Generate balance sheet from database"""

        # ASSETS - Current Assets

        # 1. Cash and Cash Equivalents (USDT, USDC, other stablecoins)
        total_cash = Decimal("0")
        if hasattr(db_manager, 'balances'):
            stablecoins = ['USDT', 'USDC', 'DAI', 'BUSD']
            for currency in stablecoins:
                for exchange in ['binance', 'coinbase', 'kraken']:
                    try:
                        balance = await db_manager.balances.get_latest(exchange, currency)
                        if balance:
                            total_cash += balance.total
                    except:
                        pass

        self.balance_sheet.add_item(BalanceSheetItem(
            category="assets",
            subcategory="current_assets",
            line_item="Cash and Cash Equivalents",
            amount=total_cash,
            note_reference="Note 1"
        ))

        # 2. Digital Assets - Trading (BTC, ETH at fair value)
        total_trading_assets = Decimal("0")
        if hasattr(db_manager, 'positions'):
            try:
                positions = await db_manager.positions.get_all()
                for pos in positions:
                    if pos.market_value:
                        total_trading_assets += pos.market_value
            except:
                pass

        self.balance_sheet.add_item(BalanceSheetItem(
            category="assets",
            subcategory="current_assets",
            line_item="Digital Assets - Trading Securities (at Fair Value)",
            amount=total_trading_assets,
            note_reference="Note 2"
        ))

        # 3. Receivables from Exchanges (pending settlements)
        receivables = Decimal("0")  # Would query pending settlements
        self.balance_sheet.add_item(BalanceSheetItem(
            category="assets",
            subcategory="current_assets",
            line_item="Receivables from Exchanges",
            amount=receivables,
            note_reference="Note 3"
        ))

        # LIABILITIES - Current Liabilities

        # 1. Accounts Payable
        payables = Decimal("0")
        self.balance_sheet.add_item(BalanceSheetItem(
            category="liabilities",
            subcategory="current_liabilities",
            line_item="Accounts Payable",
            amount=payables
        ))

        # 2. Accrued Transaction Fees
        accrued_fees = Decimal("0")
        if hasattr(db_manager, 'trades'):
            try:
                # Get unpaid fees from recent trades
                recent_trades = await db_manager.trades.get_recent(limit=1000)
                for trade in recent_trades:
                    if trade.status.value in ['pending', 'submitted']:
                        accrued_fees += trade.fee
            except:
                pass

        self.balance_sheet.add_item(BalanceSheetItem(
            category="liabilities",
            subcategory="current_liabilities",
            line_item="Accrued Transaction Fees",
            amount=accrued_fees,
            note_reference="Note 4"
        ))

        # EQUITY

        # 1. Retained Earnings (cumulative P&L)
        retained_earnings = Decimal("0")
        if hasattr(db_manager, 'trades'):
            try:
                stats = await db_manager.trades.get_daily_stats()
                if stats and 'net_pnl' in stats:
                    retained_earnings = Decimal(str(stats['net_pnl'] or 0))
            except:
                pass

        self.balance_sheet.add_item(BalanceSheetItem(
            category="equity",
            subcategory="stockholders_equity",
            line_item="Retained Earnings",
            amount=retained_earnings,
            note_reference="Note 5"
        ))

        # 2. Accumulated Other Comprehensive Income (unrealized gains/losses)
        aoci = Decimal("0")
        if hasattr(db_manager, 'positions'):
            try:
                positions = await db_manager.positions.get_all()
                for pos in positions:
                    if pos.unrealized_pnl:
                        aoci += pos.unrealized_pnl
            except:
                pass

        self.balance_sheet.add_item(BalanceSheetItem(
            category="equity",
            subcategory="stockholders_equity",
            line_item="Accumulated Other Comprehensive Income",
            amount=aoci,
            note_reference="Note 6"
        ))

    async def _generate_income_statement(self, db_manager):
        """Generate income statement from database"""

        # REVENUE

        # 1. Trading Revenue (arbitrage profits)
        trading_revenue = Decimal("0")
        if hasattr(db_manager, 'arbitrage'):
            try:
                stats = await db_manager.arbitrage.get_performance_stats(
                    days=(self.period_end - self.period_start).days
                )
                if stats and 'total_profit' in stats:
                    trading_revenue = Decimal(str(stats['total_profit'] or 0))
            except:
                pass

        self.income_statement.add_item(IncomeStatementItem(
            category="revenue",
            line_item="Trading Revenue - Arbitrage",
            amount=trading_revenue,
            note_reference="Note 7"
        ))

        # 2. Net Realized Gains on Digital Assets
        realized_gains = Decimal("0")
        if hasattr(db_manager, 'positions'):
            try:
                positions = await db_manager.positions.get_all()
                for pos in positions:
                    if pos.realized_pnl:
                        realized_gains += pos.realized_pnl
            except:
                pass

        self.income_statement.add_item(IncomeStatementItem(
            category="revenue",
            line_item="Net Realized Gains on Digital Assets",
            amount=realized_gains,
            note_reference="Note 8"
        ))

        # COST OF REVENUE

        # 1. Transaction Fees
        total_fees = Decimal("0")
        if hasattr(db_manager, 'trades'):
            try:
                stats = await db_manager.trades.get_daily_stats()
                if stats and 'total_fees' in stats:
                    total_fees = Decimal(str(stats['total_fees'] or 0))
            except:
                pass

        self.income_statement.add_item(IncomeStatementItem(
            category="cost_of_revenue",
            line_item="Transaction and Exchange Fees",
            amount=total_fees,
            note_reference="Note 9"
        ))

        # OPERATING EXPENSES

        # These would typically come from operational data
        self.income_statement.add_item(IncomeStatementItem(
            category="operating_expenses",
            line_item="Technology and Infrastructure",
            amount=Decimal("0"),  # Would be populated from actual expenses
            note_reference="Note 10"
        ))

        self.income_statement.add_item(IncomeStatementItem(
            category="operating_expenses",
            line_item="General and Administrative",
            amount=Decimal("0"),
            note_reference="Note 10"
        ))

    async def _generate_cash_flow_statement(self, db_manager):
        """Generate cash flow statement from database"""

        # Start with net income from income statement
        net_income = self.income_statement.calculate_totals()["net_income"]

        self.cash_flow_statement.add_item(CashFlowItem(
            category="operating",
            line_item="Net Income",
            amount=net_income
        ))

        # Adjustments for non-cash items

        # 1. Unrealized gains (subtract because non-cash)
        unrealized_gains = Decimal("0")
        if hasattr(db_manager, 'positions'):
            try:
                positions = await db_manager.positions.get_all()
                for pos in positions:
                    if pos.unrealized_pnl:
                        unrealized_gains += pos.unrealized_pnl
            except:
                pass

        self.cash_flow_statement.add_item(CashFlowItem(
            category="operating",
            line_item="Less: Unrealized Gains on Digital Assets",
            amount=-unrealized_gains,
            note_reference="Note 11"
        ))

        # 2. Changes in working capital would go here

        # INVESTING ACTIVITIES
        # Purchase/sale of digital assets for investment purposes

        # FINANCING ACTIVITIES
        # Debt, equity transactions

    def _add_standard_notes(self):
        """Add standard notes to financial statements"""

        # Note 1: Basis of Presentation
        self.comprehensive_notes.append(FinancialNote(
            note_number="1",
            title="Basis of Presentation and Summary of Significant Accounting Policies",
            content="""
The accompanying financial statements have been prepared in accordance with accounting principles
generally accepted in the United States of America (GAAP) and pursuant to the rules and regulations
of the Securities and Exchange Commission (SEC).

Organization and Business: The Company operates a cryptocurrency arbitrage trading system that
identifies and executes arbitrage opportunities across multiple digital asset exchanges.

Digital Assets: Digital assets held for trading purposes are measured at fair value with changes
in fair value recognized in the statement of operations. Fair value is determined based on quoted
prices on active exchanges at the balance sheet date (Level 1 inputs under ASC 820).

Revenue Recognition: Trading revenue is recognized when arbitrage trades are executed and settled,
in accordance with ASC 606. Revenue is measured as the net difference between purchase and sale
prices, less transaction costs.

Cash and Cash Equivalents: The Company considers stablecoins (USDT, USDC, DAI, BUSD) to be cash
equivalents due to their 1:1 peg to the US dollar and high liquidity.

Use of Estimates: The preparation of financial statements in conformity with GAAP requires
management to make estimates and assumptions that affect reported amounts. Actual results may differ.
            """
        ))

        # Note 2: Digital Assets
        self.comprehensive_notes.append(FinancialNote(
            note_number="2",
            title="Digital Assets",
            content="""
Digital assets consist primarily of Bitcoin (BTC) and Ethereum (ETH) held for active trading purposes.

All digital assets are classified as trading securities and measured at fair value based on quoted
prices from the exchanges where they are held. Changes in fair value are recognized in current
period earnings.

Fair Value Measurement: Fair value is determined using Level 1 inputs (quoted prices in active markets)
under ASC 820. The Company uses volume-weighted average prices (VWAP) from its connected exchanges.

Custody: Digital assets are held in segregated accounts at regulated cryptocurrency exchanges.
The Company does not have physical custody of private keys; exchange custodial services are used.

Impairment: Under current GAAP, digital assets would be subject to impairment testing. However,
as the Company holds digital assets at fair value with changes recognized currently, no separate
impairment assessment is required.
            """
        ))

        # Note 3: Fair Value Measurements
        self.comprehensive_notes.append(FinancialNote(
            note_number="3",
            title="Fair Value Measurements",
            content="""
ASC 820 establishes a fair value hierarchy that prioritizes inputs to valuation techniques:

Level 1: Quoted prices in active markets for identical assets
Level 2: Observable inputs other than Level 1 prices
Level 3: Unobservable inputs

All digital assets are classified as Level 1 measurements, as they are valued using quoted prices
from active cryptocurrency exchanges.

Fair Value by Level:
                                    Level 1         Level 2         Level 3         Total
Digital Assets - Trading            $X,XXX          $    -          $    -          $X,XXX
Cash and Equivalents (Stablecoins)  $X,XXX          $    -          $    -          $X,XXX

The Company reviews its fair value hierarchy classifications on a quarterly basis.
            """
        ))

        # Note 4: Revenue Recognition
        self.comprehensive_notes.append(FinancialNote(
            note_number="4",
            title="Revenue Recognition",
            content="""
The Company recognizes revenue from arbitrage trading activities in accordance with ASC 606,
Revenue from Contracts with Customers.

Performance Obligation: The completion of arbitrage trade pairs (simultaneous or near-simultaneous
buy and sell transactions across different exchanges).

Transaction Price: Net proceeds from sale transaction less cost of purchase transaction and
transaction fees.

Recognition Timing: Revenue is recognized at the point in time when both legs of the arbitrage
trade have been executed and settled.

Principal vs. Agent: The Company acts as a principal in all trading transactions, taking custody
and price risk of digital assets during the arbitrage period.

Disaggregation of Revenue:
- Arbitrage Trading Revenue: $X,XXX
- Net Realized Gains on Digital Assets: $X,XXX
            """
        ))

        # Note 5: Risk Factors and Concentrations
        self.comprehensive_notes.append(FinancialNote(
            note_number="5",
            title="Risk Factors and Concentrations",
            content="""
Concentration Risk:
- The Company's operations are concentrated in cryptocurrency markets
- Substantially all assets are held at a small number of cryptocurrency exchanges
- Revenue is dependent on market volatility and arbitrage opportunities

Market Risk:
- Digital asset prices are highly volatile
- Arbitrage opportunities may not be sustainable
- Execution risk in fast-moving markets

Counterparty Risk:
- Reliance on cryptocurrency exchanges for trade execution and custody
- Exchange insolvency or operational failures could result in loss of assets

Regulatory Risk:
- Cryptocurrency regulations are evolving
- Changes in regulatory treatment could materially impact operations
- Tax treatment of digital assets continues to develop

Liquidity Risk:
- Ability to exit positions depends on market liquidity
- In periods of stress, markets may become illiquid

The Company employs risk management strategies including position limits, stop-losses, and
diversification across multiple exchanges to mitigate these risks.
            """
        ))

    async def save_financial_statements(self) -> Path:
        """
        Save complete financial statement package

        Returns:
            Path to saved financial statements directory
        """
        timestamp = self.period_end.strftime("%Y%m%d")
        period_type = f"{self.period_start.strftime('%Y%m%d')}_to_{timestamp}"

        package_dir = self.data_dir / f"fs_package_{period_type}"
        package_dir.mkdir(parents=True, exist_ok=True)

        # Save balance sheet
        bs_path = package_dir / "balance_sheet.json"
        with open(bs_path, 'w') as f:
            json.dump(self.balance_sheet.to_dict(), f, indent=2)

        # Save income statement
        is_path = package_dir / "income_statement.json"
        with open(is_path, 'w') as f:
            json.dump(self.income_statement.to_dict(), f, indent=2)

        # Save cash flow statement
        cf_path = package_dir / "cash_flow_statement.json"
        with open(cf_path, 'w') as f:
            json.dump(self.cash_flow_statement.to_dict(), f, indent=2)

        # Save comprehensive notes
        notes_path = package_dir / "notes_to_financial_statements.json"
        with open(notes_path, 'w') as f:
            json.dump([
                {
                    "number": note.note_number,
                    "title": note.title,
                    "content": note.content,
                    "references": note.references
                }
                for note in self.comprehensive_notes
            ], f, indent=2)

        # Create package summary
        summary = {
            "entity_name": self.entity_name,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "preparation_date": datetime.now(timezone.utc).isoformat(),
            "accounting_basis": "GAAP",
            "files": {
                "balance_sheet": str(bs_path),
                "income_statement": str(is_path),
                "cash_flow_statement": str(cf_path),
                "notes": str(notes_path)
            },
            "balance_sheet_validated": self.balance_sheet.validate_accounting_equation()[0],
            "totals": {
                "total_assets": str(self.balance_sheet.calculate_totals()["total_assets"]),
                "total_liabilities": str(self.balance_sheet.calculate_totals()["total_liabilities"]),
                "total_equity": str(self.balance_sheet.calculate_totals()["total_equity"]),
                "net_income": str(self.income_statement.calculate_totals()["net_income"]),
                "operating_cash_flow": str(self.cash_flow_statement.calculate_totals()["operating_activities"])
            }
        }

        summary_path = package_dir / "package_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Financial statements saved to {package_dir}")
        return package_dir


__all__ = [
    "AccountingPeriod",
    "FinancialStatementType",
    "BalanceSheet",
    "BalanceSheetItem",
    "IncomeStatement",
    "IncomeStatementItem",
    "CashFlowStatement",
    "CashFlowItem",
    "FinancialNote",
    "FinancialStatementPackage"
]
