"""Redis cache wrapper with TLS support"""
import json
import os
import ssl
import redis.asyncio as redis
import logging
from decimal import Decimal
from datetime import datetime
from typing import Optional

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


def create_ssl_context(
    ca_cert_path: Optional[str] = None,
    client_cert_path: Optional[str] = None,
    client_key_path: Optional[str] = None,
    verify_mode: str = "required"
) -> ssl.SSLContext:
    """
    Create SSL context for Redis TLS connections.

    Args:
        ca_cert_path: Path to CA certificate file
        client_cert_path: Path to client certificate file (for mutual TLS)
        client_key_path: Path to client key file (for mutual TLS)
        verify_mode: Certificate verification mode ("required", "optional", "none")

    Returns:
        Configured SSL context
    """
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

    # Set verification mode
    if verify_mode == "none":
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    elif verify_mode == "optional":
        context.check_hostname = False
        context.verify_mode = ssl.CERT_OPTIONAL
    else:  # required (default)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

    # Load CA certificate
    if ca_cert_path and os.path.exists(ca_cert_path):
        context.load_verify_locations(ca_cert_path)
        logger.debug(f"Loaded CA certificate from {ca_cert_path}")

    # Load client certificate for mutual TLS
    if client_cert_path and client_key_path:
        if os.path.exists(client_cert_path) and os.path.exists(client_key_path):
            context.load_cert_chain(client_cert_path, client_key_path)
            logger.debug("Loaded client certificate for mutual TLS")

    return context


class RedisCache:
    """
    Redis cache client with TLS/SSL support.

    Supports:
    - Standard Redis connections
    - TLS encrypted connections (rediss://)
    - Mutual TLS authentication
    - Connection pooling
    """

    def __init__(self, config):
        self.config = config
        self.client = None
        self._ssl_context = None

    def _get_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Get or create SSL context if TLS is enabled."""
        use_tls = (
            os.getenv('REDIS_TLS', '').lower() in ('true', '1', 'yes') or
            self.config.get('tls', False)
        )

        if not use_tls:
            return None

        if self._ssl_context:
            return self._ssl_context

        # Get TLS configuration
        ca_cert = os.getenv('REDIS_CA_CERT', self.config.get('ca_cert', ''))
        client_cert = os.getenv('REDIS_CLIENT_CERT', self.config.get('client_cert', ''))
        client_key = os.getenv('REDIS_CLIENT_KEY', self.config.get('client_key', ''))
        verify_mode = os.getenv('REDIS_TLS_VERIFY', self.config.get('tls_verify', 'required'))

        self._ssl_context = create_ssl_context(
            ca_cert_path=ca_cert if ca_cert else None,
            client_cert_path=client_cert if client_cert else None,
            client_key_path=client_key if client_key else None,
            verify_mode=verify_mode
        )

        return self._ssl_context

    async def connect(self):
        """
        Connect to Redis server.

        Automatically uses TLS if REDIS_TLS environment variable is set
        or tls: true is in config.
        """
        host = os.getenv('REDIS_HOST', self.config.get('host', 'localhost'))
        port = int(os.getenv('REDIS_PORT', self.config.get('port', 6379)))
        password = os.getenv('REDIS_PASSWORD', self.config.get('password', ''))

        ssl_context = self._get_ssl_context()

        connection_kwargs = {
            'host': host,
            'port': port,
            'password': password if password else None,
            'decode_responses': True,
            'socket_timeout': self.config.get('socket_timeout', 5),
            'socket_connect_timeout': self.config.get('socket_connect_timeout', 5),
            'max_connections': self.config.get('max_connections', 10),
        }

        if ssl_context:
            connection_kwargs['ssl'] = ssl_context
            logger.info(f"Connecting to Redis with TLS at {host}:{port}")
        else:
            logger.info(f"Connecting to Redis at {host}:{port}")

        self.client = redis.Redis(**connection_kwargs)

        # Test connection
        try:
            await self.client.ping()
            if ssl_context:
                logger.info("Redis cache connected with TLS encryption")
            else:
                logger.info("Redis cache connected (unencrypted)")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

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

    async def delete(self, key):
        """Delete a key from cache"""
        if self.client:
            try:
                await self.client.delete(key)
            except Exception as e:
                logger.warning(f"Redis delete error for key {key}: {e}")

    async def exists(self, key) -> bool:
        """Check if a key exists"""
        if not self.client:
            return False
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.warning(f"Redis exists error for key {key}: {e}")
            return False

    async def close(self):
        if self.client:
            await self.client.close()
            logger.info("Redis cache connection closed")
