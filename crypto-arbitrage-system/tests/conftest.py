"""
Pytest configuration and shared fixtures

Provides common fixtures for all test modules:
- Mock database connections
- Mock exchange clients
- Sample data generators
- Async test support
"""

import sys
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Any
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import json


# Configure pytest-asyncio
pytest_plugins = ['pytest_asyncio']


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_trade_data() -> Dict[str, Any]:
    """Sample trade data for testing"""
    return {
        "trade_id": "test_trade_001",
        "timestamp": datetime.now(timezone.utc),
        "symbol": "BTC/USDT",
        "buy_exchange": "binance",
        "sell_exchange": "coinbase",
        "buy_price": Decimal("67000.00"),
        "sell_price": Decimal("67150.00"),
        "quantity": Decimal("0.1"),
        "buy_fee": Decimal("6.70"),
        "sell_fee": Decimal("6.72"),
        "gross_profit": Decimal("15.00"),
        "net_profit": Decimal("1.58"),
        "execution_time_ms": 245,
        "status": "completed"
    }


@pytest.fixture
def sample_orderbook_data() -> Dict[str, Any]:
    """Sample orderbook data for testing"""
    return {
        "exchange": "binance",
        "symbol": "BTC/USDT",
        "timestamp": datetime.now(timezone.utc),
        "bids": [
            (Decimal("67000"), Decimal("1.0")),
            (Decimal("66990"), Decimal("2.0")),
            (Decimal("66980"), Decimal("3.0")),
        ],
        "asks": [
            (Decimal("67100"), Decimal("1.0")),
            (Decimal("67110"), Decimal("2.0")),
            (Decimal("67120"), Decimal("3.0")),
        ]
    }


@pytest.fixture
def sample_sentiment_data() -> Dict[str, Any]:
    """Sample sentiment data for testing"""
    return {
        "timestamp": datetime.now(timezone.utc),
        "source": "fear_greed_index",
        "asset": "MARKET",
        "score": 45.0,
        "classification": "fear",
        "raw_value": {"value": "45", "value_classification": "Fear"}
    }


@pytest.fixture
def mock_db_manager():
    """Mock database manager for testing"""
    mock = AsyncMock()
    mock.trades = AsyncMock()
    mock.trades.get_recent = AsyncMock(return_value=[])
    mock.trades.get_daily_stats = AsyncMock(return_value={"net_pnl": 100.0, "total_fees": 10.0})
    mock.positions = AsyncMock()
    mock.positions.get_all = AsyncMock(return_value=[])
    mock.balances = AsyncMock()
    mock.balances.get_latest = AsyncMock(return_value=None)
    mock.arbitrage = AsyncMock()
    mock.arbitrage.get_performance_stats = AsyncMock(return_value={"total_profit": 500.0})
    return mock


@pytest.fixture
def mock_exchange_client():
    """Mock exchange client for testing"""
    mock = AsyncMock()
    mock.fetch_order_book = AsyncMock(return_value={
        "bids": [[67000, 1.0], [66990, 2.0]],
        "asks": [[67100, 1.0], [67110, 2.0]],
        "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)
    })
    mock.create_order = AsyncMock(return_value={
        "id": "order_123",
        "status": "filled",
        "filled": 0.1,
        "price": 67000
    })
    mock.fetch_balance = AsyncMock(return_value={
        "USDT": {"free": 10000, "used": 0, "total": 10000},
        "BTC": {"free": 0.5, "used": 0, "total": 0.5}
    })
    return mock


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing"""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=True)
    mock.hget = AsyncMock(return_value=None)
    mock.hset = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory for testing"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "logs").mkdir()
    (data_dir / "audit").mkdir()
    return data_dir


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Sample configuration for testing"""
    return {
        "trading": {
            "mode": "paper",
            "min_spread_percent": 0.3,
            "max_position_usd": 500,
            "max_daily_loss_usd": 100,
            "max_daily_trades": 20
        },
        "exchanges": {
            "enabled": ["binance", "coinbase"],
            "binance": {"rate_limit": 1200},
            "coinbase": {"rate_limit": 300}
        },
        "risk": {
            "max_drawdown_percent": 5.0,
            "max_position_percent": 10.0
        }
    }


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp session for API testing"""
    mock_session = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={})
    mock_session.get = AsyncMock(return_value=mock_response)
    mock_session.post = AsyncMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


# Markers for different test categories
def pytest_configure(config):
    """Configure custom markers"""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "security: marks tests as security tests")
