"""
Compliance module data models

Dataclasses for tax lots, dispositions, and trade journal entries.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List


@dataclass
class TaxLot:
    """
    Individual tax lot for cost basis tracking

    Each acquisition creates a new lot with its own cost basis.
    Dispositions consume lots according to the selected method.
    """
    lot_id: str
    asset: str
    quantity: Decimal
    cost_basis_per_unit: Decimal  # In USD
    cost_basis_total: Decimal
    acquisition_date: datetime
    acquisition_type: str  # "purchase", "trade", "airdrop", "mining", etc.
    exchange: str
    transaction_id: str
    remaining_quantity: Decimal = None
    is_closed: bool = False

    def __post_init__(self):
        if self.remaining_quantity is None:
            self.remaining_quantity = self.quantity


@dataclass
class DispositionRecord:
    """Record of asset disposition for tax purposes"""
    disposition_id: str
    asset: str
    quantity: Decimal
    proceeds_per_unit: Decimal  # In USD
    proceeds_total: Decimal
    disposition_date: datetime
    disposition_type: str  # "sale", "trade", "transfer"
    exchange: str
    transaction_id: str

    # Cost basis from consumed lots
    cost_basis_total: Decimal = Decimal("0")
    gain_loss: Decimal = Decimal("0")
    is_short_term: bool = True  # < 1 year holding

    # Lot consumption details
    lots_consumed: List[Dict] = field(default_factory=list)


@dataclass
class TradeJournalEntry:
    """
    GAAP-compliant trade journal entry

    Captures all required information for:
    - Financial reporting
    - Tax compliance
    - Audit trail
    """
    entry_id: str
    timestamp: datetime

    # Trade details
    trade_type: str  # "arbitrage", "rebalance", "manual"
    buy_exchange: str
    sell_exchange: str
    asset_pair: str  # e.g., "BTC/USD"

    # Quantities and prices
    buy_quantity: Decimal
    buy_price: Decimal
    buy_total_usd: Decimal
    buy_fees_usd: Decimal

    sell_quantity: Decimal
    sell_price: Decimal
    sell_total_usd: Decimal
    sell_fees_usd: Decimal

    # P&L
    gross_profit_usd: Decimal
    total_fees_usd: Decimal
    net_profit_usd: Decimal
    spread_percentage: Decimal

    # Execution details
    execution_time_ms: int
    slippage_bps: int

    # Risk metrics at time of trade
    portfolio_value_usd: Decimal
    position_size_percentage: Decimal

    # Verification
    entry_hash: str = ""
    verified: bool = False
