"""
Data Exporter

Export data for accountants and auditors in various formats.
"""

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict

import aiofiles

from .enums import TaxJurisdiction
from .cost_basis import CostBasisTracker
from .journal import TradeJournal

logger = logging.getLogger(__name__)


class DataExporter:
    """
    Export data for accountants and auditors

    Supports:
    - CSV for spreadsheet import
    - JSON for programmatic access
    - Tax-specific formats (Form 8949, etc.)
    """

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data/exports")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    async def export_trades_csv(
        self,
        journal: TradeJournal,
        filename: str = None,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Path:
        """Export trades to CSV for accountants"""
        if filename is None:
            filename = f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        filepath = self.data_dir / filename
        entries = journal._entries

        if start_date:
            entries = [e for e in entries if e.timestamp >= start_date]
        if end_date:
            entries = [e for e in entries if e.timestamp <= end_date]

        async with aiofiles.open(filepath, 'w', newline='') as f:
            # Write header
            header = [
                "Entry ID", "Timestamp", "Trade Type",
                "Buy Exchange", "Sell Exchange", "Asset Pair",
                "Buy Quantity", "Buy Price", "Buy Total USD", "Buy Fees USD",
                "Sell Quantity", "Sell Price", "Sell Total USD", "Sell Fees USD",
                "Gross Profit USD", "Total Fees USD", "Net Profit USD",
                "Spread %", "Execution Time (ms)", "Slippage (bps)",
                "Portfolio Value USD", "Position Size %"
            ]
            await f.write(",".join(header) + "\n")

            # Write entries
            for e in entries:
                row = [
                    e.entry_id,
                    e.timestamp.isoformat(),
                    e.trade_type,
                    e.buy_exchange,
                    e.sell_exchange,
                    e.asset_pair,
                    str(e.buy_quantity),
                    str(e.buy_price),
                    str(e.buy_total_usd),
                    str(e.buy_fees_usd),
                    str(e.sell_quantity),
                    str(e.sell_price),
                    str(e.sell_total_usd),
                    str(e.sell_fees_usd),
                    str(e.gross_profit_usd),
                    str(e.total_fees_usd),
                    str(e.net_profit_usd),
                    str(e.spread_percentage),
                    str(e.execution_time_ms),
                    str(e.slippage_bps),
                    str(e.portfolio_value_usd),
                    str(e.position_size_percentage)
                ]
                await f.write(",".join(row) + "\n")

        logger.info(f"Exported {len(entries)} trades to {filepath}")
        return filepath

    async def export_tax_report(
        self,
        cost_tracker: CostBasisTracker,
        tax_year: int,
        jurisdiction: TaxJurisdiction = TaxJurisdiction.US
    ) -> Path:
        """
        Export tax report for specified year

        For US: Compatible with Form 8949 format
        """
        filename = f"tax_report_{tax_year}_{jurisdiction.value}.csv"
        filepath = self.data_dir / filename

        # Filter dispositions for tax year
        start = datetime(tax_year, 1, 1, tzinfo=timezone.utc)
        end = datetime(tax_year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

        dispositions = [
            d for d in cost_tracker._dispositions
            if start <= d.disposition_date <= end
        ]

        async with aiofiles.open(filepath, 'w', newline='') as f:
            if jurisdiction == TaxJurisdiction.US:
                # Form 8949 compatible format
                header = [
                    "Description", "Date Acquired", "Date Sold",
                    "Proceeds", "Cost Basis", "Gain or Loss",
                    "Short/Long Term", "Transaction ID"
                ]
                await f.write(",".join(header) + "\n")

                for d in dispositions:
                    # Get acquisition date from first consumed lot
                    acq_date = ""
                    if d.lots_consumed:
                        acq_date = d.lots_consumed[0].get("acquisition_date", "Various")

                    term = "Short" if d.is_short_term else "Long"

                    row = [
                        f"{d.quantity} {d.asset}",
                        acq_date,
                        d.disposition_date.strftime("%Y-%m-%d"),
                        str(d.proceeds_total.quantize(Decimal("0.01"))),
                        str(d.cost_basis_total.quantize(Decimal("0.01"))),
                        str(d.gain_loss.quantize(Decimal("0.01"))),
                        term,
                        d.transaction_id
                    ]
                    await f.write(",".join(row) + "\n")

        logger.info(f"Exported tax report to {filepath}")
        return filepath

    async def export_audit_package(
        self,
        journal: TradeJournal,
        cost_tracker: CostBasisTracker,
        start_date: datetime,
        end_date: datetime
    ) -> Path:
        """
        Export complete audit package

        Includes:
        - Trade journal with hash verification
        - Tax lot details
        - P&L summary
        - Integrity verification results
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        audit_dir = self.data_dir / f"audit_package_{timestamp}"
        audit_dir.mkdir(parents=True, exist_ok=True)

        # Export trade journal
        await self.export_trades_csv(journal, "trades.csv", start_date, end_date)

        # Verify integrity
        is_valid, invalid_entries = journal.verify_integrity()

        # Create summary
        summary = {
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "trade_summary": {
                k: str(v) if isinstance(v, Decimal) else v
                for k, v in journal.get_summary(start_date, end_date).items()
            },
            "integrity_check": {
                "is_valid": is_valid,
                "invalid_entries": invalid_entries
            },
            "cost_basis_method": cost_tracker.method.value,
            "open_positions": {}
        }

        # Add open positions
        for asset, lots in cost_tracker._lots.items():
            open_lots = [l for l in lots if not l.is_closed]
            if open_lots:
                summary["open_positions"][asset] = {
                    "quantity": str(sum(l.remaining_quantity for l in open_lots)),
                    "total_cost_basis": str(sum(
                        l.remaining_quantity * l.cost_basis_per_unit
                        for l in open_lots
                    )),
                    "lot_count": len(open_lots)
                }

        # Write summary
        async with aiofiles.open(audit_dir / "audit_summary.json", 'w') as f:
            await f.write(json.dumps(summary, indent=2))

        logger.info(f"Exported audit package to {audit_dir}")
        return audit_dir
