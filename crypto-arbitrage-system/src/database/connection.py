"""Database connection pool manager"""
import os
import asyncpg
import logging

logger = logging.getLogger(__name__)


class DatabasePool:
    def __init__(self, config):
        self.config = config
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            host=os.getenv('DB_HOST', self.config.get('host', 'localhost')),
            port=int(os.getenv('DB_PORT', self.config.get('port', 5432))),
            database=os.getenv('DB_NAME', self.config.get('database', 'arbitrage')),
            user=os.getenv('DB_USER', self.config.get('user', 'arbitrage_user')),
            password=os.getenv('DB_PASSWORD', self.config.get('password', '')),
            min_size=self.config.get('pool_min_size', 2),
            max_size=self.config.get('pool_max_size', 10),
            command_timeout=self.config.get('command_timeout', 60)
        )
        logger.info("Database pool connected")

    def acquire(self):
        return self.pool.acquire()

    async def close(self):
        if self.pool:
            await self.pool.close()
