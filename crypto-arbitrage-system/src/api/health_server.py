"""
Health HTTP Server

Simple HTTP server exposing health check endpoints:
- GET /health - Full health check (readiness)
- GET /live - Liveness probe (just returns 200)
- GET /ready - Readiness probe (checks dependencies)
- GET /metrics - Prometheus metrics

Designed for Kubernetes probes and monitoring systems.
"""

import asyncio
import json
import logging
from aiohttp import web
from typing import Optional

from .health import HealthChecker, DatabaseHealthCheck, RedisHealthCheck, ExchangeHealthCheck, HealthStatus

logger = logging.getLogger(__name__)


class HealthServer:
    """
    HTTP server for health endpoints.

    Usage:
        health_server = HealthServer(
            port=8080,
            db_pool=db_pool,
            redis_client=cache,
            exchanges=exchanges
        )
        await health_server.start()
        # ... later ...
        await health_server.stop()
    """

    def __init__(
        self,
        port: int = 8080,
        db_pool = None,
        redis_client = None,
        exchanges: dict = None,
        version: str = "1.0.0"
    ):
        self.port = port
        self.health_checker = HealthChecker(version=version)

        # Register dependency health checks
        if db_pool:
            self.health_checker.register_check(
                "database",
                DatabaseHealthCheck(db_pool)
            )

        if redis_client:
            self.health_checker.register_check(
                "redis",
                RedisHealthCheck(redis_client)
            )

        if exchanges:
            for name, exchange in exchanges.items():
                self.health_checker.register_check(
                    f"exchange_{name}",
                    ExchangeHealthCheck(exchange, name)
                )

        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None

    async def start(self):
        """Start the health HTTP server"""
        self._app = web.Application()

        # Register routes
        self._app.router.add_get("/health", self._health_handler)
        self._app.router.add_get("/live", self._liveness_handler)
        self._app.router.add_get("/ready", self._readiness_handler)
        self._app.router.add_get("/", self._root_handler)

        # Start server
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await self._site.start()

        logger.info(f"Health server started on port {self.port}")
        logger.info(f"  - GET /health - Full health check")
        logger.info(f"  - GET /live   - Liveness probe")
        logger.info(f"  - GET /ready  - Readiness probe")

    async def stop(self):
        """Stop the health HTTP server"""
        if self._runner:
            await self._runner.cleanup()
            logger.info("Health server stopped")

    async def _root_handler(self, request: web.Request) -> web.Response:
        """Root endpoint - basic info"""
        return web.json_response({
            "service": "CARBS",
            "version": self.health_checker.version,
            "endpoints": ["/health", "/live", "/ready"]
        })

    async def _liveness_handler(self, request: web.Request) -> web.Response:
        """Liveness probe - just check if process is running"""
        is_alive = await self.health_checker.liveness()

        if is_alive:
            return web.json_response(
                {"status": "alive"},
                status=200
            )
        else:
            return web.json_response(
                {"status": "dead"},
                status=503
            )

    async def _readiness_handler(self, request: web.Request) -> web.Response:
        """Readiness probe - check if ready to serve traffic"""
        is_ready = await self.health_checker.readiness()

        if is_ready:
            return web.json_response(
                {"status": "ready"},
                status=200
            )
        else:
            return web.json_response(
                {"status": "not_ready"},
                status=503
            )

    async def _health_handler(self, request: web.Request) -> web.Response:
        """Full health check with details"""
        health = await self.health_checker.check_health()

        status_code = 200
        if health.status == HealthStatus.UNHEALTHY:
            status_code = 503
        elif health.status == HealthStatus.DEGRADED:
            status_code = 200  # Still serve traffic but alert

        return web.json_response(
            health.to_dict(),
            status=status_code
        )


async def create_health_server(
    port: int = 8080,
    db_pool = None,
    redis_client = None,
    exchanges: dict = None,
    version: str = "1.0.0"
) -> HealthServer:
    """
    Factory function to create and start a health server.

    Args:
        port: HTTP port to listen on
        db_pool: Database connection pool
        redis_client: Redis client
        exchanges: Dict of exchange instances
        version: Application version

    Returns:
        Started HealthServer instance
    """
    server = HealthServer(
        port=port,
        db_pool=db_pool,
        redis_client=redis_client,
        exchanges=exchanges,
        version=version
    )
    await server.start()
    return server
