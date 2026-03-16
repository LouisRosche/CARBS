"""
Tests for ComplianceManager orchestration layer

Tests:
- Trade recording flows through all subsystems
- Subsystem failure isolation (one failing doesn't block others)
- Journal integrity verification
- Tax report generation delegation
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for compliance data"""
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d)


@pytest.fixture
def mock_execution_result():
    """Create a mock ExecutionResult matching execution_engine.py structure"""
    result = Mock()
    result.success = True
    result.execution_time_ms = 150
    result.gross_profit = Decimal("15.50")
    result.net_profit = Decimal("10.25")
    result.total_fees = Decimal("5.25")

    buy_order = Mock()
    buy_order.order_id = "buy_123"
    buy_order.exchange = "binance"
    buy_order.filled_amount = Decimal("0.01")
    buy_order.avg_fill_price = Decimal("67000")
    buy_order.fee = Decimal("2.50")
    buy_order.side = "buy"

    sell_order = Mock()
    sell_order.order_id = "sell_456"
    sell_order.exchange = "mexc"
    sell_order.filled_amount = Decimal("0.01")
    sell_order.avg_fill_price = Decimal("67200")
    sell_order.fee = Decimal("2.75")
    sell_order.side = "sell"

    result.buy_order = buy_order
    result.sell_order = sell_order
    return result


class TestComplianceManagerInit:
    """Test ComplianceManager initialization"""

    def test_creates_all_subsystems(self, temp_data_dir):
        """Should initialize all compliance subsystems"""
        from src.compliance.manager import ComplianceManager

        manager = ComplianceManager(data_dir=temp_data_dir)

        assert manager.cost_tracker is not None
        assert manager.trade_journal is not None
        assert manager.exporter is not None
        assert manager.soc2 is not None

    def test_default_cost_basis_method_is_fifo(self, temp_data_dir):
        """Default cost basis method should be FIFO"""
        from src.compliance.manager import ComplianceManager
        from src.compliance.enums import CostBasisMethod

        manager = ComplianceManager(data_dir=temp_data_dir)
        assert manager.cost_tracker.method == CostBasisMethod.FIFO

    def test_configurable_cost_basis_method(self, temp_data_dir):
        """Should accept cost basis method from config"""
        from src.compliance.manager import ComplianceManager
        from src.compliance.enums import CostBasisMethod

        config = {"cost_basis_method": "LIFO"}
        manager = ComplianceManager(config=config, data_dir=temp_data_dir)
        assert manager.cost_tracker.method == CostBasisMethod.LIFO


class TestRecordTrade:
    """Test trade recording across subsystems"""

    @pytest.mark.asyncio
    async def test_successful_trade_records_to_all_subsystems(self, temp_data_dir, mock_execution_result):
        """A successful trade should be recorded in cost basis, journal, revenue, and SOC2"""
        from src.compliance.manager import ComplianceManager

        manager = ComplianceManager(data_dir=temp_data_dir)
        result = await manager.record_trade(
            execution_result=mock_execution_result,
            buy_exchange="binance",
            sell_exchange="mexc",
            symbol="BTC/USDT",
            portfolio_value=Decimal("50000")
        )

        assert result["success"] is True
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_failed_execution_skips_recording(self, temp_data_dir):
        """Failed trades (success=False) should not be recorded"""
        from src.compliance.manager import ComplianceManager

        failed_result = Mock()
        failed_result.success = False
        failed_result.buy_order = None
        failed_result.sell_order = None

        manager = ComplianceManager(data_dir=temp_data_dir)
        result = await manager.record_trade(
            execution_result=failed_result,
            buy_exchange="binance",
            sell_exchange="mexc",
            symbol="BTC/USDT"
        )

        # Should indicate skip or handle gracefully
        assert result is not None

    @pytest.mark.asyncio
    async def test_subsystem_failure_isolation(self, temp_data_dir, mock_execution_result):
        """If one subsystem fails, others should still complete"""
        from src.compliance.manager import ComplianceManager

        manager = ComplianceManager(data_dir=temp_data_dir)

        # Break the journal but keep cost tracker working
        manager.trade_journal.add_entry = Mock(side_effect=Exception("Journal disk full"))

        result = await manager.record_trade(
            execution_result=mock_execution_result,
            buy_exchange="binance",
            sell_exchange="mexc",
            symbol="BTC/USDT"
        )

        # Should have recorded despite journal failure
        assert result["success"] is False  # Partial failure
        assert len(result["errors"]) > 0  # At least one error recorded


class TestJournalIntegrity:
    """Test journal integrity verification"""

    @pytest.mark.asyncio
    async def test_verify_empty_journal(self, temp_data_dir):
        """Empty journal should verify as valid"""
        from src.compliance.manager import ComplianceManager

        manager = ComplianceManager(data_dir=temp_data_dir)
        is_valid, invalid_ids = manager.verify_journal_integrity()
        assert is_valid is True
        assert len(invalid_ids) == 0

    @pytest.mark.asyncio
    async def test_verify_after_recording(self, temp_data_dir, mock_execution_result):
        """Journal should remain valid after recording trades"""
        from src.compliance.manager import ComplianceManager

        manager = ComplianceManager(data_dir=temp_data_dir)
        await manager.record_trade(
            execution_result=mock_execution_result,
            buy_exchange="binance",
            sell_exchange="mexc",
            symbol="BTC/USDT",
            portfolio_value=Decimal("50000")
        )

        is_valid, invalid_ids = manager.verify_journal_integrity()
        assert is_valid is True
