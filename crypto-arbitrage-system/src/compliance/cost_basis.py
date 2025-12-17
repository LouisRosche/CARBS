"""
Cost Basis Tracking

Tracks cost basis using configurable methods (FIFO, LIFO, HIFO, Specific).
"""

import json
import hashlib
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List

from .enums import CostBasisMethod
from .models import TaxLot, DispositionRecord

logger = logging.getLogger(__name__)


class CostBasisTracker:
    """
    Tracks cost basis using configurable methods

    Supports:
    - FIFO: First lots acquired are first sold
    - LIFO: Last lots acquired are first sold
    - HIFO: Highest cost lots sold first (tax optimization)
    - Specific: Manual lot selection
    """

    def __init__(
        self,
        method: CostBasisMethod = CostBasisMethod.FIFO,
        data_dir: Path = None
    ):
        self.method = method
        self.data_dir = data_dir or Path("data/compliance")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Tax lots by asset
        self._lots: Dict[str, List[TaxLot]] = {}

        # Disposition history
        self._dispositions: List[DispositionRecord] = []

        # Load existing data
        self._load_data()

    @property
    def lots(self) -> Dict[str, List[TaxLot]]:
        """Get all tax lots"""
        return self._lots

    def _load_data(self):
        """Load existing tax lot data"""
        lots_file = self.data_dir / "tax_lots.json"
        if lots_file.exists():
            try:
                with open(lots_file) as f:
                    data = json.load(f)
                    for asset, lots in data.items():
                        self._lots[asset] = [
                            TaxLot(
                                lot_id=lot["lot_id"],
                                asset=lot["asset"],
                                quantity=Decimal(lot["quantity"]),
                                cost_basis_per_unit=Decimal(lot["cost_basis_per_unit"]),
                                cost_basis_total=Decimal(lot["cost_basis_total"]),
                                acquisition_date=datetime.fromisoformat(lot["acquisition_date"]),
                                acquisition_type=lot["acquisition_type"],
                                exchange=lot["exchange"],
                                transaction_id=lot["transaction_id"],
                                remaining_quantity=Decimal(lot["remaining_quantity"]),
                                is_closed=lot["is_closed"]
                            )
                            for lot in lots
                        ]
            except Exception as e:
                logger.error(f"Failed to load tax lots: {e}")

    def _save_data(self):
        """Persist tax lot data"""
        lots_file = self.data_dir / "tax_lots.json"
        data = {}
        for asset, lots in self._lots.items():
            data[asset] = [
                {
                    "lot_id": lot.lot_id,
                    "asset": lot.asset,
                    "quantity": str(lot.quantity),
                    "cost_basis_per_unit": str(lot.cost_basis_per_unit),
                    "cost_basis_total": str(lot.cost_basis_total),
                    "acquisition_date": lot.acquisition_date.isoformat(),
                    "acquisition_type": lot.acquisition_type,
                    "exchange": lot.exchange,
                    "transaction_id": lot.transaction_id,
                    "remaining_quantity": str(lot.remaining_quantity),
                    "is_closed": lot.is_closed
                }
                for lot in lots
            ]

        with open(lots_file, 'w') as f:
            json.dump(data, f, indent=2)

    def add_lot(
        self,
        asset: str,
        quantity: Decimal,
        cost_basis_per_unit: Decimal,
        acquisition_date: datetime,
        acquisition_type: str,
        exchange: str,
        transaction_id: str
    ) -> TaxLot:
        """
        Record new asset acquisition (alias for add_acquisition)

        Creates a new tax lot for cost basis tracking.
        """
        return self.add_acquisition(
            asset, quantity, cost_basis_per_unit,
            acquisition_date, acquisition_type, exchange, transaction_id
        )

    def add_acquisition(
        self,
        asset: str,
        quantity: Decimal,
        cost_per_unit: Decimal,
        acquisition_date: datetime,
        acquisition_type: str,
        exchange: str,
        transaction_id: str
    ) -> TaxLot:
        """
        Record new asset acquisition

        Creates a new tax lot for cost basis tracking.
        """
        lot_id = hashlib.sha256(
            f"{asset}:{transaction_id}:{acquisition_date.isoformat()}".encode()
        ).hexdigest()[:16]

        lot = TaxLot(
            lot_id=lot_id,
            asset=asset,
            quantity=quantity,
            cost_basis_per_unit=cost_per_unit,
            cost_basis_total=quantity * cost_per_unit,
            acquisition_date=acquisition_date,
            acquisition_type=acquisition_type,
            exchange=exchange,
            transaction_id=transaction_id
        )

        if asset not in self._lots:
            self._lots[asset] = []
        self._lots[asset].append(lot)

        self._save_data()
        logger.info(f"Added tax lot {lot_id}: {quantity} {asset} @ ${cost_per_unit}")

        return lot

    def dispose(
        self,
        asset: str,
        quantity: Decimal,
        proceeds_per_unit: Decimal,
        disposition_date: datetime,
        disposition_type: str,
        exchange: str,
        transaction_id: str,
        specific_lots: List[str] = None
    ) -> DispositionRecord:
        """
        Record asset disposition (alias for record_disposition)
        """
        return self.record_disposition(
            asset, quantity, proceeds_per_unit, disposition_date,
            disposition_type, exchange, transaction_id, specific_lots
        )

    def record_disposition(
        self,
        asset: str,
        quantity: Decimal,
        proceeds_per_unit: Decimal,
        disposition_date: datetime,
        disposition_type: str,
        exchange: str,
        transaction_id: str,
        specific_lots: List[str] = None
    ) -> DispositionRecord:
        """
        Record asset disposition and calculate gain/loss

        Consumes tax lots according to the configured method.
        Returns disposition record with gain/loss calculation.
        """
        # Check if we have enough quantity
        available = self.get_available_quantity(asset)
        if available < quantity:
            raise ValueError(
                f"Insufficient {asset} for disposition: "
                f"need {quantity}, have {available}"
            )

        disposition_id = hashlib.sha256(
            f"{asset}:{transaction_id}:{disposition_date.isoformat()}".encode()
        ).hexdigest()[:16]

        record = DispositionRecord(
            disposition_id=disposition_id,
            asset=asset,
            quantity=quantity,
            proceeds_per_unit=proceeds_per_unit,
            proceeds_total=quantity * proceeds_per_unit,
            disposition_date=disposition_date,
            disposition_type=disposition_type,
            exchange=exchange,
            transaction_id=transaction_id
        )

        # Get lots to consume
        lots = self._get_lots_for_disposition(
            asset, quantity, disposition_date, specific_lots
        )

        remaining_qty = quantity
        total_cost_basis = Decimal("0")

        for lot in lots:
            if remaining_qty <= 0:
                break

            consume_qty = min(remaining_qty, lot.remaining_quantity)
            cost_basis = consume_qty * lot.cost_basis_per_unit

            record.lots_consumed.append({
                "lot_id": lot.lot_id,
                "quantity": str(consume_qty),
                "cost_basis": str(cost_basis),
                "acquisition_date": lot.acquisition_date.isoformat(),
                "holding_period_days": (disposition_date - lot.acquisition_date).days
            })

            # Check if short-term (< 1 year)
            holding_days = (disposition_date - lot.acquisition_date).days
            if holding_days >= 365:
                record.is_short_term = False

            total_cost_basis += cost_basis
            lot.remaining_quantity -= consume_qty

            if lot.remaining_quantity <= 0:
                lot.is_closed = True

            remaining_qty -= consume_qty

        if remaining_qty > 0:
            logger.warning(
                f"Insufficient lots for disposition: {remaining_qty} {asset} uncovered"
            )

        record.cost_basis_total = total_cost_basis
        record.gain_loss = record.proceeds_total - total_cost_basis

        self._dispositions.append(record)
        self._save_data()

        logger.info(
            f"Disposition {disposition_id}: {quantity} {asset}, "
            f"gain/loss: ${record.gain_loss:.2f} "
            f"({'short' if record.is_short_term else 'long'}-term)"
        )

        return record

    def _get_lots_for_disposition(
        self,
        asset: str,
        quantity: Decimal,
        disposition_date: datetime,
        specific_lots: List[str] = None
    ) -> List[TaxLot]:
        """Get lots to consume based on method"""
        if asset not in self._lots:
            return []

        # Filter to open lots
        open_lots = [lot for lot in self._lots[asset] if not lot.is_closed]

        if specific_lots:
            # Specific lot identification
            return [
                lot for lot in open_lots
                if lot.lot_id in specific_lots
            ]

        # Sort based on method
        if self.method == CostBasisMethod.FIFO:
            open_lots.sort(key=lambda x: x.acquisition_date)
        elif self.method == CostBasisMethod.LIFO:
            open_lots.sort(key=lambda x: x.acquisition_date, reverse=True)
        elif self.method == CostBasisMethod.HIFO:
            open_lots.sort(key=lambda x: x.cost_basis_per_unit, reverse=True)

        return open_lots

    def get_available_quantity(self, asset: str) -> Decimal:
        """Get available quantity for an asset"""
        if asset not in self._lots:
            return Decimal("0")

        return sum(
            lot.remaining_quantity
            for lot in self._lots[asset]
            if not lot.is_closed
        )

    def get_total_cost_basis(self, asset: str) -> Decimal:
        """Get total cost basis for an asset"""
        if asset not in self._lots:
            return Decimal("0")

        return sum(
            lot.remaining_quantity * lot.cost_basis_per_unit
            for lot in self._lots[asset]
            if not lot.is_closed
        )

    def get_unrealized_gains(self, asset: str, current_price: Decimal) -> Dict:
        """Calculate unrealized gains for an asset"""
        if asset not in self._lots:
            return {"total_quantity": Decimal("0"), "unrealized_gain": Decimal("0")}

        open_lots = [lot for lot in self._lots[asset] if not lot.is_closed]

        total_qty = sum(lot.remaining_quantity for lot in open_lots)
        total_cost = sum(
            lot.remaining_quantity * lot.cost_basis_per_unit
            for lot in open_lots
        )
        current_value = total_qty * current_price

        return {
            "total_quantity": total_qty,
            "total_cost_basis": total_cost,
            "current_value": current_value,
            "unrealized_gain": current_value - total_cost,
            "average_cost": total_cost / total_qty if total_qty > 0 else Decimal("0")
        }
