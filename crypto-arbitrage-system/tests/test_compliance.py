"""
Tests for compliance and accounting module

Tests:
- Cost basis tracking (FIFO, LIFO, HIFO)
- Tax lot management
- Trade journaling
- GAAP financial statement generation
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile

from compliance import (
    CostBasisMethod,
    AssetClass,
    TaxJurisdiction,
    TaxLot,
    DispositionRecord,
    TradeJournalEntry,
    CostBasisTracker,
)


class TestTaxLot:
    """Tests for TaxLot dataclass"""

    def test_tax_lot_creation(self):
        """Should create tax lot with all required fields"""
        lot = TaxLot(
            lot_id="lot_001",
            asset="BTC",
            quantity=Decimal("1.0"),
            cost_basis_per_unit=Decimal("67000"),
            cost_basis_total=Decimal("67000"),
            acquisition_date=datetime.now(timezone.utc),
            acquisition_type="purchase",
            exchange="binance",
            transaction_id="tx_001"
        )

        assert lot.lot_id == "lot_001"
        assert lot.asset == "BTC"
        assert lot.quantity == Decimal("1.0")
        assert lot.remaining_quantity == Decimal("1.0")
        assert lot.is_closed is False

    def test_tax_lot_remaining_quantity_initialized(self):
        """Remaining quantity should equal initial quantity"""
        lot = TaxLot(
            lot_id="lot_002",
            asset="ETH",
            quantity=Decimal("10.0"),
            cost_basis_per_unit=Decimal("3500"),
            cost_basis_total=Decimal("35000"),
            acquisition_date=datetime.now(timezone.utc),
            acquisition_type="trade",
            exchange="coinbase",
            transaction_id="tx_002"
        )

        assert lot.remaining_quantity == lot.quantity


class TestDispositionRecord:
    """Tests for DispositionRecord dataclass"""

    def test_disposition_record_creation(self):
        """Should create disposition record"""
        record = DispositionRecord(
            disposition_id="disp_001",
            asset="BTC",
            quantity=Decimal("0.5"),
            proceeds_per_unit=Decimal("68000"),
            proceeds_total=Decimal("34000"),
            disposition_date=datetime.now(timezone.utc),
            disposition_type="sale",
            exchange="binance",
            transaction_id="tx_003"
        )

        assert record.disposition_id == "disp_001"
        assert record.quantity == Decimal("0.5")
        assert record.cost_basis_total == Decimal("0")
        assert record.is_short_term is True

    def test_disposition_gain_loss_calculation(self):
        """Should track gain/loss on disposition"""
        record = DispositionRecord(
            disposition_id="disp_002",
            asset="BTC",
            quantity=Decimal("1.0"),
            proceeds_per_unit=Decimal("70000"),
            proceeds_total=Decimal("70000"),
            disposition_date=datetime.now(timezone.utc),
            disposition_type="sale",
            exchange="coinbase",
            transaction_id="tx_004",
            cost_basis_total=Decimal("65000"),
            gain_loss=Decimal("5000")
        )

        assert record.gain_loss == Decimal("5000")


class TestTradeJournalEntry:
    """Tests for TradeJournalEntry dataclass"""

    def test_journal_entry_creation(self):
        """Should create complete journal entry"""
        entry = TradeJournalEntry(
            entry_id="entry_001",
            timestamp=datetime.now(timezone.utc),
            trade_type="arbitrage",
            buy_exchange="binance",
            sell_exchange="coinbase",
            asset_pair="BTC/USD",
            buy_quantity=Decimal("0.1"),
            buy_price=Decimal("67000"),
            buy_total_usd=Decimal("6700"),
            buy_fees_usd=Decimal("6.70"),
            sell_quantity=Decimal("0.1"),
            sell_price=Decimal("67150"),
            sell_total_usd=Decimal("6715"),
            sell_fees_usd=Decimal("6.72"),
            gross_profit_usd=Decimal("15.00"),
            total_fees_usd=Decimal("13.42"),
            net_profit_usd=Decimal("1.58"),
            spread_percentage=Decimal("0.224"),
            execution_time_ms=245,
            slippage_bps=5,
            portfolio_value_usd=Decimal("10000"),
            position_size_percentage=Decimal("6.7")
        )

        assert entry.entry_id == "entry_001"
        assert entry.trade_type == "arbitrage"
        assert entry.net_profit_usd == Decimal("1.58")


class TestCostBasisTracker:
    """Tests for CostBasisTracker"""

    @pytest.fixture
    def tracker_fifo(self, temp_data_dir):
        """Create FIFO tracker"""
        return CostBasisTracker(
            method=CostBasisMethod.FIFO,
            data_dir=temp_data_dir
        )

    @pytest.fixture
    def tracker_lifo(self, temp_data_dir):
        """Create LIFO tracker"""
        return CostBasisTracker(
            method=CostBasisMethod.LIFO,
            data_dir=temp_data_dir
        )

    @pytest.fixture
    def tracker_hifo(self, temp_data_dir):
        """Create HIFO tracker"""
        return CostBasisTracker(
            method=CostBasisMethod.HIFO,
            data_dir=temp_data_dir
        )

    def test_add_lot(self, tracker_fifo):
        """Should add new tax lot"""
        lot = tracker_fifo.add_lot(
            asset="BTC",
            quantity=Decimal("1.0"),
            cost_basis_per_unit=Decimal("67000"),
            acquisition_date=datetime.now(timezone.utc),
            acquisition_type="purchase",
            exchange="binance",
            transaction_id="tx_001"
        )

        assert lot is not None
        assert lot.asset == "BTC"
        assert len(tracker_fifo.lots) == 1

    def test_fifo_disposition(self, tracker_fifo):
        """FIFO should sell oldest lots first"""
        # Add lots at different prices
        tracker_fifo.add_lot(
            asset="BTC",
            quantity=Decimal("1.0"),
            cost_basis_per_unit=Decimal("65000"),
            acquisition_date=datetime.now(timezone.utc) - timedelta(days=30),
            acquisition_type="purchase",
            exchange="binance",
            transaction_id="tx_001"
        )
        tracker_fifo.add_lot(
            asset="BTC",
            quantity=Decimal("1.0"),
            cost_basis_per_unit=Decimal("70000"),
            acquisition_date=datetime.now(timezone.utc),
            acquisition_type="purchase",
            exchange="binance",
            transaction_id="tx_002"
        )

        # Dispose 0.5 BTC
        record = tracker_fifo.dispose(
            asset="BTC",
            quantity=Decimal("0.5"),
            proceeds_per_unit=Decimal("68000"),
            disposition_date=datetime.now(timezone.utc),
            disposition_type="sale",
            exchange="coinbase",
            transaction_id="tx_003"
        )

        # Should use the $65000 lot (oldest)
        assert record.cost_basis_total == Decimal("32500")  # 0.5 * 65000
        assert record.gain_loss == Decimal("1500")  # (68000 - 65000) * 0.5

    def test_lifo_disposition(self, tracker_lifo):
        """LIFO should sell newest lots first"""
        # Add lots at different prices
        tracker_lifo.add_lot(
            asset="BTC",
            quantity=Decimal("1.0"),
            cost_basis_per_unit=Decimal("65000"),
            acquisition_date=datetime.now(timezone.utc) - timedelta(days=30),
            acquisition_type="purchase",
            exchange="binance",
            transaction_id="tx_001"
        )
        tracker_lifo.add_lot(
            asset="BTC",
            quantity=Decimal("1.0"),
            cost_basis_per_unit=Decimal("70000"),
            acquisition_date=datetime.now(timezone.utc),
            acquisition_type="purchase",
            exchange="binance",
            transaction_id="tx_002"
        )

        # Dispose 0.5 BTC
        record = tracker_lifo.dispose(
            asset="BTC",
            quantity=Decimal("0.5"),
            proceeds_per_unit=Decimal("68000"),
            disposition_date=datetime.now(timezone.utc),
            disposition_type="sale",
            exchange="coinbase",
            transaction_id="tx_003"
        )

        # Should use the $70000 lot (newest)
        assert record.cost_basis_total == Decimal("35000")  # 0.5 * 70000
        assert record.gain_loss == Decimal("-1000")  # (68000 - 70000) * 0.5

    def test_hifo_disposition(self, tracker_hifo):
        """HIFO should sell highest cost lots first"""
        # Add lots at different prices
        tracker_hifo.add_lot(
            asset="BTC",
            quantity=Decimal("1.0"),
            cost_basis_per_unit=Decimal("65000"),
            acquisition_date=datetime.now(timezone.utc) - timedelta(days=30),
            acquisition_type="purchase",
            exchange="binance",
            transaction_id="tx_001"
        )
        tracker_hifo.add_lot(
            asset="BTC",
            quantity=Decimal("1.0"),
            cost_basis_per_unit=Decimal("70000"),
            acquisition_date=datetime.now(timezone.utc),
            acquisition_type="purchase",
            exchange="binance",
            transaction_id="tx_002"
        )

        # Dispose 0.5 BTC
        record = tracker_hifo.dispose(
            asset="BTC",
            quantity=Decimal("0.5"),
            proceeds_per_unit=Decimal("68000"),
            disposition_date=datetime.now(timezone.utc),
            disposition_type="sale",
            exchange="coinbase",
            transaction_id="tx_003"
        )

        # Should use the $70000 lot (highest cost - minimizes gains)
        assert record.cost_basis_total == Decimal("35000")  # 0.5 * 70000

    def test_insufficient_quantity(self, tracker_fifo):
        """Should raise error if insufficient quantity"""
        tracker_fifo.add_lot(
            asset="BTC",
            quantity=Decimal("0.5"),
            cost_basis_per_unit=Decimal("67000"),
            acquisition_date=datetime.now(timezone.utc),
            acquisition_type="purchase",
            exchange="binance",
            transaction_id="tx_001"
        )

        with pytest.raises(ValueError, match="Insufficient"):
            tracker_fifo.dispose(
                asset="BTC",
                quantity=Decimal("1.0"),  # More than available
                proceeds_per_unit=Decimal("68000"),
                disposition_date=datetime.now(timezone.utc),
                disposition_type="sale",
                exchange="coinbase",
                transaction_id="tx_002"
            )

    def test_short_term_vs_long_term(self, tracker_fifo):
        """Should correctly classify short-term vs long-term gains"""
        # Add lot from more than 1 year ago
        old_date = datetime.now(timezone.utc) - timedelta(days=400)
        tracker_fifo.add_lot(
            asset="BTC",
            quantity=Decimal("1.0"),
            cost_basis_per_unit=Decimal("50000"),
            acquisition_date=old_date,
            acquisition_type="purchase",
            exchange="binance",
            transaction_id="tx_001"
        )

        # Dispose now
        record = tracker_fifo.dispose(
            asset="BTC",
            quantity=Decimal("0.5"),
            proceeds_per_unit=Decimal("68000"),
            disposition_date=datetime.now(timezone.utc),
            disposition_type="sale",
            exchange="coinbase",
            transaction_id="tx_002"
        )

        # Should be long-term (held > 1 year)
        assert record.is_short_term is False

    def test_get_total_cost_basis(self, tracker_fifo):
        """Should calculate total cost basis for asset"""
        tracker_fifo.add_lot(
            asset="BTC",
            quantity=Decimal("1.0"),
            cost_basis_per_unit=Decimal("65000"),
            acquisition_date=datetime.now(timezone.utc),
            acquisition_type="purchase",
            exchange="binance",
            transaction_id="tx_001"
        )
        tracker_fifo.add_lot(
            asset="BTC",
            quantity=Decimal("0.5"),
            cost_basis_per_unit=Decimal("70000"),
            acquisition_date=datetime.now(timezone.utc),
            acquisition_type="purchase",
            exchange="binance",
            transaction_id="tx_002"
        )

        total = tracker_fifo.get_total_cost_basis("BTC")
        assert total == Decimal("100000")  # 65000 + 35000


class TestCostBasisMethod:
    """Tests for CostBasisMethod enum"""

    def test_all_methods_defined(self):
        """Should have all standard cost basis methods"""
        assert CostBasisMethod.FIFO.value == "fifo"
        assert CostBasisMethod.LIFO.value == "lifo"
        assert CostBasisMethod.HIFO.value == "hifo"
        assert CostBasisMethod.SPECIFIC.value == "specific"


class TestAssetClass:
    """Tests for AssetClass enum"""

    def test_all_asset_classes_defined(self):
        """Should have all asset classes"""
        assert AssetClass.CRYPTOCURRENCY.value == "cryptocurrency"
        assert AssetClass.STABLECOIN.value == "stablecoin"
        assert AssetClass.DEFI_TOKEN.value == "defi_token"
        assert AssetClass.NFT.value == "nft"
        assert AssetClass.FIAT.value == "fiat"


class TestTaxJurisdiction:
    """Tests for TaxJurisdiction enum"""

    def test_all_jurisdictions_defined(self):
        """Should have all tax jurisdictions"""
        assert TaxJurisdiction.US.value == "us"
        assert TaxJurisdiction.UK.value == "uk"
        assert TaxJurisdiction.EU.value == "eu"
        assert TaxJurisdiction.CANADA.value == "canada"
        assert TaxJurisdiction.AUSTRALIA.value == "australia"
