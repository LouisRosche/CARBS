"""
Database connection pool manager with proper resource cleanup.

Implements:
- Context manager support for guaranteed cleanup
- Connection health verification
- Graceful shutdown
- Connection retry on failure
"""
import os
import asyncio
import asyncpg
import logging
from contextlib import asynccontextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class ConnectionError(Exception):
    """Raised when database connection fails"""
    pass


class DatabasePool:
    """
    Database connection pool with proper lifecycle management.

    Features:
    - Async context manager support
    - Connection health checks
    - Graceful cleanup on exit
    - Automatic retry on connection failure
    """

    def __init__(self, config: dict):
        """
        Initialize database pool.

        Args:
            config: Database configuration dictionary
        """
        if config is None:
            raise ValueError("Database config cannot be None")

        self.config = config
        self.pool: Optional[asyncpg.Pool] = None
        self._connected = False
        self._shutdown_lock = asyncio.Lock()
        self._max_retries = config.get('max_connect_retries', 3)
        self._retry_delay = config.get('connect_retry_delay', 2)

    @property
    def is_connected(self) -> bool:
        """Check if pool is connected and healthy"""
        return self._connected and self.pool is not None

    async def connect(self) -> None:
        """
        Connect to database with retry logic.

        Raises:
            ConnectionError: If unable to connect after retries
        """
        if self._connected and self.pool:
            logger.debug("Database pool already connected")
            return

        last_error = None

        for attempt in range(self._max_retries):
            try:
                self.pool = await asyncpg.create_pool(
                    host=os.getenv('DB_HOST', self.config.get('host', 'localhost')),
                    port=int(os.getenv('DB_PORT', self.config.get('port', 5432))),
                    database=os.getenv('DB_NAME', self.config.get('database', 'arbitrage')),
                    user=os.getenv('DB_USER', self.config.get('user', 'arbitrage_user')),
                    password=os.getenv('DB_PASSWORD', self.config.get('password', '')),
                    min_size=self.config.get('pool_min_size', 2),
                    max_size=self.config.get('pool_max_size', 10),
                    command_timeout=self.config.get('command_timeout', 60),
                    # Connection timeout for initial connection
                    timeout=self.config.get('connect_timeout', 30)
                )

                # Verify connection by running simple query
                async with self.pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")

                self._connected = True
                logger.info(
                    f"Database pool connected (min={self.config.get('pool_min_size', 2)}, "
                    f"max={self.config.get('pool_max_size', 10)})"
                )
                return

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Database connection attempt {attempt + 1}/{self._max_retries} failed: {e}"
                )
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))

        raise ConnectionError(
            f"Failed to connect to database after {self._max_retries} attempts: {last_error}"
        )

    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a connection from the pool.

        Yields:
            asyncpg.Connection: Database connection

        Raises:
            ConnectionError: If pool is not connected
        """
        if not self._connected or not self.pool:
            raise ConnectionError("Database pool not connected. Call connect() first.")

        conn = None
        try:
            conn = await self.pool.acquire()
            yield conn
        finally:
            if conn:
                await self.pool.release(conn)

    async def execute(self, query: str, *args) -> str:
        """
        Execute a query directly.

        Args:
            query: SQL query
            *args: Query arguments

        Returns:
            Query result status
        """
        async with self.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> list:
        """
        Fetch multiple rows.

        Args:
            query: SQL query
            *args: Query arguments

        Returns:
            List of records
        """
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        """
        Fetch a single row.

        Args:
            query: SQL query
            *args: Query arguments

        Returns:
            Single record or None
        """
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        """
        Fetch a single value.

        Args:
            query: SQL query
            *args: Query arguments

        Returns:
            Single value or None
        """
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def health_check(self) -> bool:
        """
        Verify database connection health.

        Returns:
            True if healthy, False otherwise
        """
        if not self._connected or not self.pool:
            return False

        try:
            async with self.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def close(self) -> None:
        """
        Close the connection pool gracefully.

        Thread-safe and idempotent.
        """
        async with self._shutdown_lock:
            if self.pool:
                try:
                    # Wait for connections to be released
                    await asyncio.wait_for(
                        self.pool.close(),
                        timeout=10.0
                    )
                    logger.info("Database pool closed gracefully")
                except asyncio.TimeoutError:
                    # Force termination
                    self.pool.terminate()
                    logger.warning("Database pool terminated (timeout waiting for connections)")
                except Exception as e:
                    logger.error(f"Error closing database pool: {e}")
                finally:
                    self.pool = None
                    self._connected = False

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensures cleanup"""
        await self.close()
        return False  # Don't suppress exceptions

    def __del__(self):
        """Destructor - warn if not properly closed"""
        if self._connected and self.pool:
            logger.warning(
                "DatabasePool was not properly closed. "
                "Use 'async with' or call close() explicitly."
            )


class ConnectionContextManager:
    """
    Convenience context manager for single database operations.

    Example:
        async with ConnectionContextManager(config) as conn:
            result = await conn.fetch("SELECT * FROM trades")
    """

    def __init__(self, config: dict):
        self.config = config
        self.pool = None
        self.connection = None

    async def __aenter__(self):
        self.pool = DatabasePool(self.config)
        await self.pool.connect()
        self.connection = await self.pool.pool.acquire()
        return self.connection

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.connection and self.pool and self.pool.pool:
            await self.pool.pool.release(self.connection)
        if self.pool:
            await self.pool.close()
        return False
