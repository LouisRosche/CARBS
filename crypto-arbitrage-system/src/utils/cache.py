"""Redis cache wrapper"""
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)

class RedisCache:
    def __init__(self, config):
        self.config = config
        self.client = None
    
    async def connect(self):
        self.client = redis.Redis(
            host='localhost',
            port=6379,
            password='change_me',
            decode_responses=True
        )
        logger.info("Redis cache connected")
    
    async def get(self, key):
        return await self.client.get(key) if self.client else None
    
    async def set(self, key, value, ttl=None):
        if self.client:
            await self.client.set(key, str(value), ex=ttl)
    
    async def close(self):
        if self.client:
            await self.client.close()
