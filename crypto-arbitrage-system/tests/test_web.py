"""
Tests for aiohttp health server endpoints

Tests:
- GET / returns service info
- GET /live returns liveness status
- GET /ready returns readiness status
- GET /health returns full health details
- HealthServer initialization with no dependencies
- HealthServer initialization with mock dependencies
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from aiohttp import web
from aiohttp.test_utils import TestServer, TestClient

from src.api.health_server import HealthServer


@pytest_asyncio.fixture
async def health_server():
    """Create a HealthServer with no dependencies."""
    server = HealthServer(port=0, version="1.2.3")
    return server


@pytest_asyncio.fixture
async def aiohttp_app(health_server):
    """Build the aiohttp Application from a HealthServer."""
    app = web.Application()
    app.router.add_get("/health", health_server._health_handler)
    app.router.add_get("/live", health_server._liveness_handler)
    app.router.add_get("/ready", health_server._readiness_handler)
    app.router.add_get("/", health_server._root_handler)
    return app


@pytest_asyncio.fixture
async def client(aiohttp_app):
    """Create an aiohttp TestClient for HTTP testing."""
    server = TestServer(aiohttp_app)
    client = TestClient(server)
    await client.start_server()
    yield client
    await client.close()


@pytest.mark.asyncio
async def test_root_returns_service_info(client):
    """GET / returns service info with correct keys."""
    resp = await client.get("/")
    assert resp.status == 200
    data = await resp.json()
    assert data["service"] == "CARBS"
    assert data["version"] == "1.2.3"
    assert "endpoints" in data
    assert "/health" in data["endpoints"]
    assert "/live" in data["endpoints"]
    assert "/ready" in data["endpoints"]


@pytest.mark.asyncio
async def test_liveness_returns_alive(client):
    """GET /live returns 200 with 'alive' status."""
    resp = await client.get("/live")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "alive"


@pytest.mark.asyncio
async def test_readiness_returns_ready(client):
    """GET /ready returns 200 with 'ready' status."""
    resp = await client.get("/ready")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ready"


@pytest.mark.asyncio
async def test_health_returns_full_details(client):
    """GET /health returns 200 with full health details."""
    resp = await client.get("/health")
    assert resp.status == 200
    data = await resp.json()
    assert "status" in data
    assert data["version"] == "1.2.3"
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0
    assert "checks" in data
    assert isinstance(data["checks"], list)


@pytest.mark.asyncio
async def test_health_server_init_no_dependencies():
    """HealthServer initializes correctly with no dependencies."""
    server = HealthServer(port=9090, version="0.1.0")
    assert server.port == 9090
    assert server.health_checker.version == "0.1.0"
    assert server._app is None
    assert server._runner is None
    assert server._site is None


@pytest.mark.asyncio
async def test_health_server_init_with_mock_dependencies():
    """HealthServer initializes correctly with mock db_pool, redis_client, exchanges."""
    mock_db_pool = MagicMock()
    mock_redis = AsyncMock()
    mock_exchange = AsyncMock()
    mock_exchanges = {"binance": mock_exchange}

    server = HealthServer(
        port=8080,
        db_pool=mock_db_pool,
        redis_client=mock_redis,
        exchanges=mock_exchanges,
        version="2.0.0",
    )

    assert server.port == 8080
    assert server.health_checker.version == "2.0.0"
    # The HealthServer registers dependency checks via the HealthChecker
    checks = server.health_checker._checks
    assert "database" in checks
    assert "redis" in checks
    assert "exchange_binance" in checks
