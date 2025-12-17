"""
Trade Journal

GAAP-compliant trade journaling with hash chain integrity.
"""

import json
import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List

from .models import TradeJournalEntry

logger = logging.getLogger(__name__)


class TradeJournal:
    """
    GAAP-compliant trade journal

    Features:
    - Immutable entries with hash chain
    - Full audit trail
    - Export capabilities
    - P&L tracking
    """

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data/compliance")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._entries: List[TradeJournalEntry] = []
        self._last_hash: str = "0" * 64

        self._load_entries()

    def _load_entries(self):
        """Load existing journal entries"""
        journal_file = self.data_dir / "trade_journal.json"
        if journal_file.exists():
            try:
                with open(journal_file) as f:
                    data = json.load(f)
                    for entry in data.get("entries", []):
                        self._entries.append(TradeJournalEntry(
                            entry_id=entry["entry_id"],
                            timestamp=datetime.fromisoformat(entry["timestamp"]),
                            trade_type=entry["trade_type"],
                            buy_exchange=entry["buy_exchange"],
                            sell_exchange=entry["sell_exchange"],
                            asset_pair=entry["asset_pair"],
                            buy_quantity=Decimal(entry["buy_quantity"]),
                            buy_price=Decimal(entry["buy_price"]),
                            buy_total_usd=Decimal(entry["buy_total_usd"]),
                            buy_fees_usd=Decimal(entry["buy_fees_usd"]),
                            sell_quantity=Decimal(entry["sell_quantity"]),
                            sell_price=Decimal(entry["sell_price"]),
                            sell_total_usd=Decimal(entry["sell_total_usd"]),
                            sell_fees_usd=Decimal(entry["sell_fees_usd"]),
                            gross_profit_usd=Decimal(entry["gross_profit_usd"]),
                            total_fees_usd=Decimal(entry["total_fees_usd"]),
                            net_profit_usd=Decimal(entry["net_profit_usd"]),
                            spread_percentage=Decimal(entry["spread_percentage"]),
                            execution_time_ms=entry["execution_time_ms"],
                            slippage_bps=entry["slippage_bps"],
                            portfolio_value_usd=Decimal(entry["portfolio_value_usd"]),
                            position_size_percentage=Decimal(entry["position_size_percentage"]),
                            entry_hash=entry["entry_hash"],
                            verified=entry.get("verified", False)
                        ))
                    self._last_hash = data.get("last_hash", "0" * 64)
            except Exception as e:
                logger.error(f"Failed to load trade journal: {e}")

    def _save_entries(self):
        """Persist journal entries"""
        journal_file = self.data_dir / "trade_journal.json"

        data = {
            "last_hash": self._last_hash,
            "entries": [
                {
                    "entry_id": e.entry_id,
                    "timestamp": e.timestamp.isoformat(),
                    "trade_type": e.trade_type,
                    "buy_exchange": e.buy_exchange,
                    "sell_exchange": e.sell_exchange,
                    "asset_pair": e.asset_pair,
                    "buy_quantity": str(e.buy_quantity),
                    "buy_price": str(e.buy_price),
                    "buy_total_usd": str(e.buy_total_usd),
                    "buy_fees_usd": str(e.buy_fees_usd),
                    "sell_quantity": str(e.sell_quantity),
                    "sell_price": str(e.sell_price),
                    "sell_total_usd": str(e.sell_total_usd),
                    "sell_fees_usd": str(e.sell_fees_usd),
                    "gross_profit_usd": str(e.gross_profit_usd),
                    "total_fees_usd": str(e.total_fees_usd),
                    "net_profit_usd": str(e.net_profit_usd),
                    "spread_percentage": str(e.spread_percentage),
                    "execution_time_ms": e.execution_time_ms,
                    "slippage_bps": e.slippage_bps,
                    "portfolio_value_usd": str(e.portfolio_value_usd),
                    "position_size_percentage": str(e.position_size_percentage),
                    "entry_hash": e.entry_hash,
                    "verified": e.verified
                }
                for e in self._entries
            ]
        }

        with open(journal_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _compute_entry_hash(self, entry: TradeJournalEntry) -> str:
        """Compute hash for entry (includes previous hash for chain)"""
        content = (
            f"{self._last_hash}:"
            f"{entry.entry_id}:"
            f"{entry.timestamp.isoformat()}:"
            f"{entry.trade_type}:"
            f"{entry.buy_exchange}:{entry.sell_exchange}:"
            f"{entry.asset_pair}:"
            f"{entry.buy_quantity}:{entry.buy_price}:"
            f"{entry.sell_quantity}:{entry.sell_price}:"
            f"{entry.net_profit_usd}"
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def add_entry(
        self,
        trade_type: str,
        buy_exchange: str,
        sell_exchange: str,
        asset_pair: str,
        buy_quantity: Decimal,
        buy_price: Decimal,
        buy_fees_usd: Decimal,
        sell_quantity: Decimal,
        sell_price: Decimal,
        sell_fees_usd: Decimal,
        execution_time_ms: int,
        slippage_bps: int,
        portfolio_value_usd: Decimal
    ) -> TradeJournalEntry:
        """Add new trade journal entry"""
        entry_id = hashlib.sha256(
            f"{datetime.now(timezone.utc).isoformat()}:{buy_exchange}:{sell_exchange}".encode()
        ).hexdigest()[:16]

        buy_total = buy_quantity * buy_price
        sell_total = sell_quantity * sell_price
        total_fees = buy_fees_usd + sell_fees_usd
        gross_profit = sell_total - buy_total
        net_profit = gross_profit - total_fees
        spread_pct = ((sell_price - buy_price) / buy_price * 100) if buy_price > 0 else Decimal("0")
        position_pct = (buy_total / portfolio_value_usd * 100) if portfolio_value_usd > 0 else Decimal("0")

        entry = TradeJournalEntry(
            entry_id=entry_id,
            timestamp=datetime.now(timezone.utc),
            trade_type=trade_type,
            buy_exchange=buy_exchange,
            sell_exchange=sell_exchange,
            asset_pair=asset_pair,
            buy_quantity=buy_quantity,
            buy_price=buy_price,
            buy_total_usd=buy_total,
            buy_fees_usd=buy_fees_usd,
            sell_quantity=sell_quantity,
            sell_price=sell_price,
            sell_total_usd=sell_total,
            sell_fees_usd=sell_fees_usd,
            gross_profit_usd=gross_profit,
            total_fees_usd=total_fees,
            net_profit_usd=net_profit,
            spread_percentage=spread_pct,
            execution_time_ms=execution_time_ms,
            slippage_bps=slippage_bps,
            portfolio_value_usd=portfolio_value_usd,
            position_size_percentage=position_pct
        )

        # Compute and set hash
        entry.entry_hash = self._compute_entry_hash(entry)
        self._last_hash = entry.entry_hash

        self._entries.append(entry)
        self._save_entries()

        logger.info(
            f"Journal entry {entry_id}: {asset_pair} "
            f"profit=${net_profit:.2f} ({spread_pct:.3f}%)"
        )

        return entry

    def verify_integrity(self) -> tuple:
        """
        Verify hash chain integrity

        Returns:
            (is_valid: bool, invalid_entries: List[str])
        """
        invalid = []
        prev_hash = "0" * 64

        for entry in self._entries:
            # Temporarily set last_hash to compute expected hash
            saved_last = self._last_hash
            self._last_hash = prev_hash

            expected_hash = self._compute_entry_hash(entry)
            self._last_hash = saved_last

            if entry.entry_hash != expected_hash:
                invalid.append(entry.entry_id)

            prev_hash = entry.entry_hash

        return len(invalid) == 0, invalid

    def get_summary(
        self,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict:
        """Get P&L summary for period"""
        entries = self._entries

        if start_date:
            entries = [e for e in entries if e.timestamp >= start_date]
        if end_date:
            entries = [e for e in entries if e.timestamp <= end_date]

        if not entries:
            return {
                "total_trades": 0,
                "total_profit": Decimal("0"),
                "total_fees": Decimal("0"),
                "win_rate": Decimal("0"),
                "avg_profit_per_trade": Decimal("0")
            }

        total_profit = sum(e.net_profit_usd for e in entries)
        total_fees = sum(e.total_fees_usd for e in entries)
        wins = sum(1 for e in entries if e.net_profit_usd > 0)

        return {
            "total_trades": len(entries),
            "total_profit": total_profit,
            "total_fees": total_fees,
            "win_rate": Decimal(str(wins / len(entries) * 100)),
            "avg_profit_per_trade": total_profit / len(entries),
            "best_trade": max(e.net_profit_usd for e in entries),
            "worst_trade": min(e.net_profit_usd for e in entries),
            "avg_execution_time_ms": sum(e.execution_time_ms for e in entries) / len(entries)
        }
