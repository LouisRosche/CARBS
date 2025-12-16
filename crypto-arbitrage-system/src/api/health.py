"""
Health Check and Monitoring Endpoints

Production-grade health monitoring:
- Liveness probe (is the service running)
- Readiness probe (is the service ready to accept traffic)
- Detailed health checks for dependencies
- Prometheus metrics endpoint
- System resource monitoring
"""

import asyncio
import logging
import os
import platform
import psutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    name: str
    status: HealthStatus
    message: str = ""
    duration_ms: float = 0
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SystemHealth:
    """Overall system health"""
    status: HealthStatus
    version: str
    uptime_seconds: float
    checks: List[HealthCheckResult]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        return {
            "status": self.status.value,
            "version": self.version,
            "uptime_seconds": self.uptime_seconds,
            "timestamp": self.timestamp.isoformat(),
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "duration_ms": c.duration_ms,
                    "details": c.details
                }
                for c in self.checks
            ]
        }


class HealthChecker:
    """
    Health check manager

    Supports:
    - Liveness checks (is process running)
    - Readiness checks (dependencies healthy)
    - Custom health checks
    - Dependency health aggregation
    """

    def __init__(
        self,
        version: str = "1.0.0",
        db_pool=None,
        redis_client=None,
        exchanges: Dict = None
    ):
        """
        Initialize health checker with optional dependencies.

        Args:
            version: Application version string
            db_pool: Database connection pool for health checks
            redis_client: Redis client for health checks
            exchanges: Dict of exchange instances for health checks
        """
        self.version = version
        self._start_time = datetime.now(timezone.utc)
        self._checks: Dict[str, Callable[[], Coroutine[Any, Any, HealthCheckResult]]] = {}

        # Store dependencies for actual connectivity tests
        self._db_pool = db_pool
        self._redis_client = redis_client
        self._exchanges = exchanges or {}

        # Register built-in checks
        self.register_check("memory", self._check_memory)
        self.register_check("disk", self._check_disk)
        self.register_check("cpu", self._check_cpu)

        # Register dependency checks if dependencies provided
        if db_pool is not None:
            self.register_check("database", self._check_database)

        if redis_client is not None:
            self.register_check("redis", self._check_redis)

        for exchange_name in self._exchanges:
            self.register_check(
                f"exchange_{exchange_name}",
                lambda name=exchange_name: self._check_exchange(name)
            )

    @property
    def uptime_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self._start_time).total_seconds()

    def register_check(
        self,
        name: str,
        check: Callable[[], Coroutine[Any, Any, HealthCheckResult]]
    ):
        """Register a health check"""
        self._checks[name] = check
        logger.debug(f"Registered health check: {name}")

    def unregister_check(self, name: str):
        """Remove a health check"""
        if name in self._checks:
            del self._checks[name]

    async def liveness(self) -> bool:
        """
        Liveness probe - is the service running?

        Used by Kubernetes to determine if pod should be restarted
        """
        return True

    async def readiness(self) -> bool:
        """
        Readiness probe - is the service ready for traffic?

        Used by Kubernetes to determine if pod should receive traffic
        """
        health = await self.check_health()
        return health.status != HealthStatus.UNHEALTHY

    async def check_health(self, checks: List[str] = None) -> SystemHealth:
        """
        Run health checks

        Args:
            checks: Specific checks to run (or None for all)

        Returns:
            SystemHealth with aggregated status
        """
        results = []
        target_checks = checks or list(self._checks.keys())

        for name in target_checks:
            check = self._checks.get(name)
            if not check:
                continue

            start = time.monotonic()
            try:
                result = await asyncio.wait_for(check(), timeout=10.0)
                result.duration_ms = (time.monotonic() - start) * 1000
                results.append(result)
            except asyncio.TimeoutError:
                results.append(HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message="Health check timed out",
                    duration_ms=10000
                ))
            except Exception as e:
                results.append(HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                    duration_ms=(time.monotonic() - start) * 1000
                ))

        # Aggregate status
        overall_status = HealthStatus.HEALTHY
        for result in results:
            if result.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
                break
            elif result.status == HealthStatus.DEGRADED:
                overall_status = HealthStatus.DEGRADED

        return SystemHealth(
            status=overall_status,
            version=self.version,
            uptime_seconds=self.uptime_seconds,
            checks=results
        )

    # Built-in health checks

    async def _check_memory(self) -> HealthCheckResult:
        """Check memory usage"""
        memory = psutil.virtual_memory()
        used_percent = memory.percent

        if used_percent > 90:
            status = HealthStatus.UNHEALTHY
            message = f"Memory critically high: {used_percent}%"
        elif used_percent > 80:
            status = HealthStatus.DEGRADED
            message = f"Memory usage elevated: {used_percent}%"
        else:
            status = HealthStatus.HEALTHY
            message = f"Memory usage normal: {used_percent}%"

        return HealthCheckResult(
            name="memory",
            status=status,
            message=message,
            details={
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_percent": used_percent
            }
        )

    async def _check_disk(self) -> HealthCheckResult:
        """Check disk usage"""
        disk = psutil.disk_usage('/')
        used_percent = disk.percent

        if used_percent > 95:
            status = HealthStatus.UNHEALTHY
            message = f"Disk space critical: {used_percent}%"
        elif used_percent > 85:
            status = HealthStatus.DEGRADED
            message = f"Disk space low: {used_percent}%"
        else:
            status = HealthStatus.HEALTHY
            message = f"Disk space OK: {used_percent}%"

        return HealthCheckResult(
            name="disk",
            status=status,
            message=message,
            details={
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "used_percent": used_percent
            }
        )

    async def _check_cpu(self) -> HealthCheckResult:
        """Check CPU usage"""
        cpu_percent = psutil.cpu_percent(interval=0.1)

        if cpu_percent > 95:
            status = HealthStatus.UNHEALTHY
            message = f"CPU critically high: {cpu_percent}%"
        elif cpu_percent > 80:
            status = HealthStatus.DEGRADED
            message = f"CPU usage elevated: {cpu_percent}%"
        else:
            status = HealthStatus.HEALTHY
            message = f"CPU usage normal: {cpu_percent}%"

        return HealthCheckResult(
            name="cpu",
            status=status,
            message=message,
            details={
                "cpu_percent": cpu_percent,
                "cpu_count": psutil.cpu_count(),
                "load_avg": os.getloadavg() if hasattr(os, 'getloadavg') else None
            }
        )

    async def _check_database(self) -> HealthCheckResult:
        """Check database connectivity with actual query"""
        if self._db_pool is None:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message="Database pool not configured"
            )

        try:
            async with self._db_pool.acquire() as conn:
                # Execute actual query to verify connectivity
                result = await asyncio.wait_for(
                    conn.fetchval("SELECT 1"),
                    timeout=5.0
                )

                if result == 1:
                    # Get pool stats if available
                    pool_size = getattr(self._db_pool, 'get_size', lambda: 'N/A')()
                    return HealthCheckResult(
                        name="database",
                        status=HealthStatus.HEALTHY,
                        message="Database connection OK",
                        details={"pool_size": pool_size}
                    )
                else:
                    return HealthCheckResult(
                        name="database",
                        status=HealthStatus.DEGRADED,
                        message="Database returned unexpected result"
                    )

        except asyncio.TimeoutError:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message="Database query timed out (>5s)"
            )
        except Exception as e:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {e}"
            )

    async def _check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity with actual ping"""
        if self._redis_client is None:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message="Redis client not configured"
            )

        try:
            # Execute actual ping to verify connectivity
            pong = await asyncio.wait_for(
                self._redis_client.ping(),
                timeout=5.0
            )

            if pong:
                # Get Redis info if available
                try:
                    info = await self._redis_client.info()
                    details = {
                        "version": info.get("redis_version"),
                        "connected_clients": info.get("connected_clients"),
                        "used_memory_human": info.get("used_memory_human")
                    }
                except Exception:
                    details = {}

                return HealthCheckResult(
                    name="redis",
                    status=HealthStatus.HEALTHY,
                    message="Redis connection OK",
                    details=details
                )
            else:
                return HealthCheckResult(
                    name="redis",
                    status=HealthStatus.DEGRADED,
                    message="Redis ping returned falsy value"
                )

        except asyncio.TimeoutError:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message="Redis ping timed out (>5s)"
            )
        except Exception as e:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis error: {e}"
            )

    async def _check_exchange(self, exchange_name: str) -> HealthCheckResult:
        """Check exchange connectivity with actual API call"""
        exchange = self._exchanges.get(exchange_name)
        if exchange is None:
            return HealthCheckResult(
                name=f"exchange_{exchange_name}",
                status=HealthStatus.UNHEALTHY,
                message=f"Exchange {exchange_name} not configured"
            )

        try:
            # Try to fetch a ticker - actual API call to verify connectivity
            ticker = await asyncio.wait_for(
                exchange.fetch_ticker("BTC/USDT"),
                timeout=10.0
            )

            if ticker and ticker.get('last'):
                return HealthCheckResult(
                    name=f"exchange_{exchange_name}",
                    status=HealthStatus.HEALTHY,
                    message=f"{exchange_name} connection OK",
                    details={
                        "last_price": str(ticker.get('last', 'N/A')),
                        "bid": str(ticker.get('bid', 'N/A')),
                        "ask": str(ticker.get('ask', 'N/A'))
                    }
                )
            else:
                return HealthCheckResult(
                    name=f"exchange_{exchange_name}",
                    status=HealthStatus.DEGRADED,
                    message=f"{exchange_name} returned incomplete data"
                )

        except asyncio.TimeoutError:
            return HealthCheckResult(
                name=f"exchange_{exchange_name}",
                status=HealthStatus.DEGRADED,
                message=f"{exchange_name} response slow (>10s)"
            )
        except Exception as e:
            return HealthCheckResult(
                name=f"exchange_{exchange_name}",
                status=HealthStatus.UNHEALTHY,
                message=f"{exchange_name} error: {e}"
            )


# Standalone dependency health checks (for external use)

class DatabaseHealthCheck:
    """Health check for PostgreSQL database"""

    def __init__(self, connection_pool):
        self.pool = connection_pool

    async def __call__(self) -> HealthCheckResult:
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")

                if result == 1:
                    return HealthCheckResult(
                        name="database",
                        status=HealthStatus.HEALTHY,
                        message="Database connection OK",
                        details={"pool_size": self.pool.get_size()}
                    )

        except Exception as e:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {e}"
            )


class RedisHealthCheck:
    """Health check for Redis"""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def __call__(self) -> HealthCheckResult:
        try:
            pong = await self.redis.ping()

            if pong:
                info = await self.redis.info()
                return HealthCheckResult(
                    name="redis",
                    status=HealthStatus.HEALTHY,
                    message="Redis connection OK",
                    details={
                        "version": info.get("redis_version"),
                        "connected_clients": info.get("connected_clients"),
                        "used_memory_human": info.get("used_memory_human")
                    }
                )

        except Exception as e:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis error: {e}"
            )


class ExchangeHealthCheck:
    """Health check for exchange connections"""

    def __init__(self, exchange, name: str):
        self.exchange = exchange
        self.name = name

    async def __call__(self) -> HealthCheckResult:
        try:
            # Try to get server time or simple endpoint
            ticker = await asyncio.wait_for(
                self.exchange.get_ticker("BTCUSDT"),
                timeout=5.0
            )

            if ticker:
                return HealthCheckResult(
                    name=f"exchange_{self.name}",
                    status=HealthStatus.HEALTHY,
                    message=f"{self.name} connection OK",
                    details={
                        "last_price": str(ticker.last),
                        "bid": str(ticker.bid),
                        "ask": str(ticker.ask)
                    }
                )

        except asyncio.TimeoutError:
            return HealthCheckResult(
                name=f"exchange_{self.name}",
                status=HealthStatus.DEGRADED,
                message=f"{self.name} response slow"
            )
        except Exception as e:
            return HealthCheckResult(
                name=f"exchange_{self.name}",
                status=HealthStatus.UNHEALTHY,
                message=f"{self.name} error: {e}"
            )


# Prometheus metrics extension

class PrometheusMetrics:
    """
    Extended Prometheus metrics for CARBS

    Collects:
    - Trading metrics
    - Exchange metrics
    - System metrics
    - API metrics
    """

    def __init__(self, port: int = 8000):
        from prometheus_client import (
            Counter, Gauge, Histogram, Summary, Info,
            start_http_server, REGISTRY
        )

        self.port = port

        # System info
        self.system_info = Info(
            'carbs_system',
            'System information'
        )
        self.system_info.info({
            'version': '1.0.0',
            'python_version': platform.python_version(),
            'platform': platform.system()
        })

        # Trading metrics
        self.trades_total = Counter(
            'carbs_trades_total',
            'Total trades executed',
            ['exchange', 'symbol', 'side', 'status']
        )

        self.trade_profit = Counter(
            'carbs_trade_profit_total',
            'Total profit from trades (USD)',
            ['exchange']
        )

        self.trade_volume = Counter(
            'carbs_trade_volume_total',
            'Total trading volume (USD)',
            ['exchange', 'symbol']
        )

        self.active_positions = Gauge(
            'carbs_active_positions',
            'Number of active positions',
            ['exchange']
        )

        # Opportunity metrics
        self.opportunities_found = Counter(
            'carbs_opportunities_found_total',
            'Total arbitrage opportunities found',
            ['symbol']
        )

        self.opportunity_spread = Histogram(
            'carbs_opportunity_spread_percent',
            'Spread percentage of opportunities',
            buckets=[0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0]
        )

        # Exchange metrics
        self.exchange_latency = Histogram(
            'carbs_exchange_latency_seconds',
            'Exchange API latency',
            ['exchange', 'endpoint'],
            buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )

        self.exchange_errors = Counter(
            'carbs_exchange_errors_total',
            'Exchange API errors',
            ['exchange', 'error_type']
        )

        self.exchange_rate_limits = Counter(
            'carbs_exchange_rate_limits_total',
            'Rate limit hits',
            ['exchange']
        )

        # Circuit breaker metrics
        self.circuit_breaker_state = Gauge(
            'carbs_circuit_breaker_state',
            'Circuit breaker state (0=closed, 1=half-open, 2=open)',
            ['name']
        )

        self.circuit_breaker_failures = Counter(
            'carbs_circuit_breaker_failures_total',
            'Circuit breaker failures',
            ['name']
        )

        # Balance metrics
        self.balance_total = Gauge(
            'carbs_balance_total',
            'Total balance (USD equivalent)',
            ['exchange', 'currency']
        )

        # Order book metrics
        self.orderbook_spread = Gauge(
            'carbs_orderbook_spread_bps',
            'Order book spread in basis points',
            ['exchange', 'symbol']
        )

        self.orderbook_depth = Gauge(
            'carbs_orderbook_depth_usd',
            'Order book depth in USD',
            ['exchange', 'symbol', 'side']
        )

        # Execution metrics
        self.execution_time = Histogram(
            'carbs_execution_time_seconds',
            'Order execution time',
            ['exchange'],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
        )

        self.slippage = Histogram(
            'carbs_slippage_bps',
            'Execution slippage in basis points',
            ['exchange', 'symbol'],
            buckets=[1, 2, 5, 10, 20, 50, 100]
        )

        # API metrics
        self.api_requests = Counter(
            'carbs_api_requests_total',
            'API requests',
            ['method', 'endpoint', 'status']
        )

        self.api_latency = Histogram(
            'carbs_api_latency_seconds',
            'API request latency',
            ['method', 'endpoint'],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
        )

        # Start metrics server
        try:
            start_http_server(port)
            logger.info(f"Prometheus metrics server started on port {port}")
        except Exception as e:
            logger.warning(f"Could not start metrics server: {e}")

    # Recording methods

    def record_trade(
        self,
        exchange: str,
        symbol: str,
        side: str,
        status: str,
        profit: float = 0,
        volume: float = 0
    ):
        """Record trade execution"""
        self.trades_total.labels(
            exchange=exchange,
            symbol=symbol,
            side=side,
            status=status
        ).inc()

        if profit != 0:
            self.trade_profit.labels(exchange=exchange).inc(profit)

        if volume > 0:
            self.trade_volume.labels(
                exchange=exchange,
                symbol=symbol
            ).inc(volume)

    def record_opportunity(self, symbol: str, spread_percent: float):
        """Record arbitrage opportunity"""
        self.opportunities_found.labels(symbol=symbol).inc()
        self.opportunity_spread.observe(spread_percent)

    def record_exchange_request(
        self,
        exchange: str,
        endpoint: str,
        latency: float,
        error: str = None
    ):
        """Record exchange API request"""
        self.exchange_latency.labels(
            exchange=exchange,
            endpoint=endpoint
        ).observe(latency)

        if error:
            self.exchange_errors.labels(
                exchange=exchange,
                error_type=error
            ).inc()

    def record_circuit_breaker(self, name: str, state: str, failure: bool = False):
        """Record circuit breaker state"""
        state_map = {"closed": 0, "half_open": 1, "open": 2}
        self.circuit_breaker_state.labels(name=name).set(state_map.get(state, 0))

        if failure:
            self.circuit_breaker_failures.labels(name=name).inc()

    def set_balance(self, exchange: str, currency: str, amount: float):
        """Set balance gauge"""
        self.balance_total.labels(
            exchange=exchange,
            currency=currency
        ).set(amount)

    def set_orderbook_metrics(
        self,
        exchange: str,
        symbol: str,
        spread_bps: float,
        bid_depth: float,
        ask_depth: float
    ):
        """Set order book metrics"""
        self.orderbook_spread.labels(
            exchange=exchange,
            symbol=symbol
        ).set(spread_bps)

        self.orderbook_depth.labels(
            exchange=exchange,
            symbol=symbol,
            side="bid"
        ).set(bid_depth)

        self.orderbook_depth.labels(
            exchange=exchange,
            symbol=symbol,
            side="ask"
        ).set(ask_depth)

    def record_execution(
        self,
        exchange: str,
        symbol: str,
        time_seconds: float,
        slippage_bps: float
    ):
        """Record execution metrics"""
        self.execution_time.labels(exchange=exchange).observe(time_seconds)
        self.slippage.labels(
            exchange=exchange,
            symbol=symbol
        ).observe(slippage_bps)

    def record_api_request(
        self,
        method: str,
        endpoint: str,
        status: int,
        latency: float
    ):
        """Record API request"""
        self.api_requests.labels(
            method=method,
            endpoint=endpoint,
            status=str(status)
        ).inc()

        self.api_latency.labels(
            method=method,
            endpoint=endpoint
        ).observe(latency)


__all__ = [
    "HealthStatus",
    "HealthCheckResult",
    "SystemHealth",
    "HealthChecker",
    "DatabaseHealthCheck",
    "RedisHealthCheck",
    "ExchangeHealthCheck",
    "PrometheusMetrics"
]
