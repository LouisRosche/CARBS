"""
Compliance Manager — Orchestration Layer

Provides a single entry point for recording executed trades across all
compliance subsystems: cost basis tracking, trade journaling, GAAP revenue
recognition, and SOC2 audit evidence.

Usage:
    manager = ComplianceManager()
    await manager.record_trade(execution_result, "binance", "kucoin", "BTC/USDT")
"""

import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .cost_basis import CostBasisTracker
from .enums import CostBasisMethod, TaxJurisdiction
from .exporter import DataExporter
from .fair_value_revenue import FairValueEngine, RevenueRecognitionEngine
from .journal import TradeJournal
from .soc2 import SOC2Controls

logger = logging.getLogger(__name__)


class ComplianceManager:
    """Orchestration layer for all compliance functions.

    Provides a single async method to record executed trades across:
    - Cost basis tracking (tax lots, dispositions)
    - Trade journal (audit trail)
    - Revenue recognition (GAAP)
    - SOC2 control evidence
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        data_dir: Optional[Path] = None,
    ) -> None:
        self._config = config or {}
        self._data_dir = data_dir or Path("data/compliance")
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # Determine cost basis method from config (default FIFO)
        method_name = self._config.get("cost_basis_method", "fifo").upper()
        try:
            cost_basis_method = CostBasisMethod[method_name]
        except KeyError:
            logger.warning(
                "Unknown cost basis method '%s', defaulting to FIFO",
                method_name,
            )
            cost_basis_method = CostBasisMethod.FIFO

        # Initialise sub-components
        self.cost_tracker = CostBasisTracker(
            method=cost_basis_method,
            data_dir=self._data_dir,
        )
        self.trade_journal = TradeJournal(data_dir=self._data_dir)
        self.exporter = DataExporter(data_dir=self._data_dir / "exports")
        self.fair_value_engine = FairValueEngine()
        self.revenue_engine = RevenueRecognitionEngine()
        self.soc2 = SOC2Controls()

        logger.info(
            "ComplianceManager initialised (data_dir=%s, cost_basis=%s)",
            self._data_dir,
            cost_basis_method.value,
        )

    # ------------------------------------------------------------------
    # Primary entry point — called after every executed trade
    # ------------------------------------------------------------------

    async def record_trade(
        self,
        execution_result: Any,
        buy_exchange: str,
        sell_exchange: str,
        symbol: str,
        portfolio_value: Decimal = Decimal("0"),
    ) -> Dict[str, Any]:
        """Record an executed trade across all compliance subsystems.

        Args:
            execution_result: An ``ExecutionResult`` from the execution engine.
            buy_exchange: Name of the exchange where the buy was placed.
            sell_exchange: Name of the exchange where the sell was placed.
            symbol: Trading pair (e.g. ``"BTC/USDT"``).
            portfolio_value: Current portfolio value in USD for position-size
                tracking.  Defaults to ``Decimal('0')``.

        Returns:
            Dict summarising what was recorded and any per-subsystem errors.
        """
        results: Dict[str, Any] = {
            "success": True,
            "errors": [],
        }

        if not execution_result.success:
            logger.debug(
                "Skipping compliance recording for failed execution: %s",
                getattr(execution_result, "error_message", "unknown"),
            )
            results["skipped"] = True
            return results

        buy_order = execution_result.buy_order
        sell_order = execution_result.sell_order
        base_asset = symbol.split("/")[0] if "/" in symbol else symbol
        now = datetime.now(timezone.utc)

        # Generate a deterministic trade id for cross-referencing
        trade_id = hashlib.sha256(
            f"{now.isoformat()}:{buy_exchange}:{sell_exchange}:{symbol}".encode()
        ).hexdigest()[:16]

        # 1. Cost basis — acquisition (buy side)
        await self._record_cost_basis(
            results, base_asset, buy_order, sell_order, buy_exchange, sell_exchange, now, trade_id
        )

        # 2. Trade journal entry
        await self._record_journal_entry(
            results, buy_order, sell_order, buy_exchange, sell_exchange,
            symbol, execution_result, portfolio_value,
        )

        # 3. Revenue recognition (GAAP ASC 606)
        await self._record_revenue(
            results, trade_id, buy_order, sell_order, now,
        )

        # 4. SOC2 control evidence
        await self._record_soc2_evidence(
            results, trade_id, buy_exchange, sell_exchange, symbol, execution_result,
        )

        if results["errors"]:
            results["success"] = False
            logger.warning(
                "Trade %s recorded with %d subsystem error(s)",
                trade_id,
                len(results["errors"]),
            )
        else:
            logger.info("Trade %s fully recorded across all compliance subsystems", trade_id)

        return results

    # ------------------------------------------------------------------
    # Delegated public methods
    # ------------------------------------------------------------------

    async def generate_tax_report(
        self,
        tax_year: int,
        jurisdiction: Optional[TaxJurisdiction] = None,
    ) -> Path:
        """Generate and export a tax report for the given year.

        Args:
            tax_year: Calendar year to report on.
            jurisdiction: Tax jurisdiction (defaults to US).

        Returns:
            Path to the generated report file.
        """
        jurisdiction = jurisdiction or TaxJurisdiction.US
        return await self.exporter.export_tax_report(
            cost_tracker=self.cost_tracker,
            tax_year=tax_year,
            jurisdiction=jurisdiction,
        )

    async def export_audit_package(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> Path:
        """Export a complete audit package for the given date range.

        Args:
            start_date: Period start (inclusive).
            end_date: Period end (inclusive).

        Returns:
            Path to the audit package directory.
        """
        return await self.exporter.export_audit_package(
            journal=self.trade_journal,
            cost_tracker=self.cost_tracker,
            start_date=start_date,
            end_date=end_date,
        )

    def verify_journal_integrity(self) -> Tuple[bool, List[str]]:
        """Verify the hash-chain integrity of the trade journal.

        Returns:
            Tuple of (is_valid, list_of_invalid_entry_ids).
        """
        return self.trade_journal.verify_integrity()

    # ------------------------------------------------------------------
    # Private helpers — each wraps one subsystem in its own try/except
    # ------------------------------------------------------------------

    async def _record_cost_basis(
        self,
        results: Dict[str, Any],
        base_asset: str,
        buy_order: Any,
        sell_order: Any,
        buy_exchange: str,
        sell_exchange: str,
        now: datetime,
        trade_id: str,
    ) -> None:
        """Record acquisition (buy) and disposition (sell) tax lots."""
        try:
            # Acquisition on the buy exchange
            lot = self.cost_tracker.add_acquisition(
                asset=base_asset,
                quantity=buy_order.filled_amount,
                cost_per_unit=buy_order.avg_fill_price,
                acquisition_date=now,
                acquisition_type="arbitrage_buy",
                exchange=buy_exchange,
                transaction_id=f"{trade_id}_buy",
            )
            results["tax_lot_id"] = lot.lot_id

            # Disposition on the sell exchange
            try:
                disposition = self.cost_tracker.record_disposition(
                    asset=base_asset,
                    quantity=sell_order.filled_amount,
                    proceeds_per_unit=sell_order.avg_fill_price,
                    disposition_date=now,
                    disposition_type="arbitrage_sell",
                    exchange=sell_exchange,
                    transaction_id=f"{trade_id}_sell",
                )
                results["disposition_id"] = disposition.disposition_id
                results["gain_loss"] = disposition.gain_loss
            except ValueError as exc:
                # Insufficient lots — log but do not block
                logger.warning("Cost basis disposition skipped: %s", exc)
                results["errors"].append(f"cost_basis_disposition: {exc}")

        except Exception as exc:
            logger.error("Cost basis recording failed: %s", exc, exc_info=True)
            results["errors"].append(f"cost_basis: {exc}")

    async def _record_journal_entry(
        self,
        results: Dict[str, Any],
        buy_order: Any,
        sell_order: Any,
        buy_exchange: str,
        sell_exchange: str,
        symbol: str,
        execution_result: Any,
        portfolio_value: Decimal,
    ) -> None:
        """Add a trade journal entry."""
        try:
            entry = self.trade_journal.add_entry(
                trade_type="arbitrage",
                buy_exchange=buy_exchange,
                sell_exchange=sell_exchange,
                asset_pair=symbol,
                buy_quantity=buy_order.filled_amount,
                buy_price=buy_order.avg_fill_price,
                buy_fees_usd=buy_order.fee,
                sell_quantity=sell_order.filled_amount,
                sell_price=sell_order.avg_fill_price,
                sell_fees_usd=sell_order.fee,
                execution_time_ms=execution_result.execution_time_ms,
                slippage_bps=0,
                portfolio_value_usd=portfolio_value,
            )
            results["journal_entry_id"] = entry.entry_id
        except Exception as exc:
            logger.error("Trade journal recording failed: %s", exc, exc_info=True)
            results["errors"].append(f"trade_journal: {exc}")

    async def _record_revenue(
        self,
        results: Dict[str, Any],
        trade_id: str,
        buy_order: Any,
        sell_order: Any,
        now: datetime,
    ) -> None:
        """Recognise revenue per ASC 606."""
        try:
            event = await self.revenue_engine.recognize_arbitrage_revenue(
                trade_id=trade_id,
                buy_price=buy_order.avg_fill_price,
                sell_price=sell_order.avg_fill_price,
                quantity=buy_order.filled_amount,
                buy_fee=buy_order.fee,
                sell_fee=sell_order.fee,
                execution_date=now,
            )
            results["revenue_event_id"] = event.event_id
        except Exception as exc:
            logger.error("Revenue recognition failed: %s", exc, exc_info=True)
            results["errors"].append(f"revenue_recognition: {exc}")

    async def _record_soc2_evidence(
        self,
        results: Dict[str, Any],
        trade_id: str,
        buy_exchange: str,
        sell_exchange: str,
        symbol: str,
        execution_result: Any,
    ) -> None:
        """Log SOC2 processing-integrity evidence for the trade."""
        try:
            self.soc2.log_control_evidence(
                control_id="PI1.1",
                control_name="Trade Processing Integrity",
                evidence_type="trade_execution",
                details={
                    "trade_id": trade_id,
                    "buy_exchange": buy_exchange,
                    "sell_exchange": sell_exchange,
                    "symbol": symbol,
                    "execution_time_ms": execution_result.execution_time_ms,
                    "gross_profit": str(execution_result.gross_profit),
                    "net_profit": str(execution_result.net_profit),
                    "total_fees": str(execution_result.total_fees),
                },
            )
            results["soc2_logged"] = True
        except Exception as exc:
            logger.error("SOC2 evidence logging failed: %s", exc, exc_info=True)
            results["errors"].append(f"soc2: {exc}")
