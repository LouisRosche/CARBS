"""Redis cache wrapper"""
import json
import os
import redis.asyncio as redis
import logging
from decimal import Decimal
from datetime import datetime

logger = logging.getLogger(__name__)


def serialize_value(value):
    """Serialize value to JSON-compatible format"""
    if isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [serialize_value(v) for v in value]
    elif isinstance(value, tuple):
        return [serialize_value(v) for v in value]
    elif isinstance(value, Decimal):
        return str(value)
    elif isinstance(value, datetime):
        return value.isoformat()
    return value


class RedisCache:
    def __init__(self, config):
        self.config = config
        self.client = None

    async def connect(self):
        self.client = redis.Redis(
            host=os.getenv('REDIS_HOST', self.config.get('host', 'localhost')),
            port=int(os.getenv('REDIS_PORT', self.config.get('port', 6379))),
            password=os.getenv('REDIS_PASSWORD', self.config.get('password', '')),
            decode_responses=True,
            socket_timeout=self.config.get('socket_timeout', 5),
            socket_connect_timeout=self.config.get('socket_connect_timeout', 5),
            max_connections=self.config.get('max_connections', 10)
        )
        logger.info("Redis cache connected")

    async def get(self, key):
        if not self.client:
            return None
        try:
            value = await self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Redis get error for key {key}: {e}")
            return None

    async def set(self, key, value, ttl=None):
        if self.client:
            try:
                serialized = json.dumps(serialize_value(value))
                await self.client.set(key, serialized, ex=ttl)
            except Exception as e:
                logger.warning(f"Redis set error for key {key}: {e}")

    async def close(self):
        if self.client:
            await self.client.close()
