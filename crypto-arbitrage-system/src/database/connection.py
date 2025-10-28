"""Database connection pool manager"""
import asyncpg
import logging

logger = logging.getLogger(__name__)

class DatabasePool:
    def __init__(self, config):
        self.config = config
        self.pool = None
    
    async def connect(self):
        self.pool = await asyncpg.create_pool(
            host='localhost',
            database='arbitrage',
            user='arbitrage_user',
            password='change_me',
            min_size=self.config.get('pool_min_size', 2),
            max_size=self.config.get('pool_max_size', 10)
        )
        logger.info("Database pool connected")
    
    def acquire(self):
        return self.pool.acquire()
    
    async def close(self):
        if self.pool:
            await self.pool.close()
