"""
Base Exchange

Abstract base class for all exchange implementations.
"""

import json
import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List, Optional

import aiohttp

from .enums import OrderSide, OrderType
from .models import Ticker, OrderBook, Balance, Order
from .rate_limiter import RateLimiter
from .exceptions import ExchangeError

logger = logging.getLogger(__name__)


class BaseExchange(ABC):
    """
    Abstract base class for exchange implementations

    All exchanges must implement these methods.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
        rate_limit: float = 10
    ):
        # Store credentials securely encrypted in memory
        from ..utils.secure_credentials import SecureString
        self._api_key = SecureString(api_key) if api_key else None
        self._api_secret = SecureString(api_secret) if api_secret else None
        self.testnet = testnet
        self.rate_limiter = RateLimiter(rate_limit)

        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None

    @property
    def api_key(self) -> str:
        """Get decrypted API key."""
        return self._api_key.get() if self._api_key else ""

    @property
    def api_secret(self) -> str:
        """Get decrypted API secret."""
        return self._api_secret.get() if self._api_secret else ""

    @property
    @abstractmethod
    def name(self) -> str:
        """Exchange name"""
        raise NotImplementedError(f"{self.__class__.__name__}.name not implemented")

    @property
    @abstractmethod
    def base_url(self) -> str:
        """API base URL"""
        raise NotImplementedError(f"{self.__class__.__name__}.base_url not implemented")

    async def _ensure_session(self):
        """Ensure aiohttp session exists with proper security and limits"""
        if self._session is None or self._session.closed:
            # Configure connection limits to prevent resource exhaustion
            connector = aiohttp.TCPConnector(
                limit=100,              # Total connection limit
                limit_per_host=30,      # Per-host limit
                ssl=True,               # Enforce SSL verification
                enable_cleanup_closed=True
            )
            # Configure timeouts to prevent hanging
            timeout = aiohttp.ClientTimeout(
                total=30,               # Total request timeout
                connect=10,             # Connection timeout
                sock_read=20            # Socket read timeout
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout
            )

    async def close(self):
        """Close connections and securely clear credentials"""
        if self._session:
            await self._session.close()
        if self._ws:
            await self._ws.close()
        # Securely clear credentials from memory
        if self._api_key:
            self._api_key.clear()
        if self._api_secret:
            self._api_secret.clear()

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        """Get current ticker"""
        raise NotImplementedError(f"{self.__class__.__name__}.get_ticker not implemented")

    @abstractmethod
    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """Get order book"""
        raise NotImplementedError(f"{self.__class__.__name__}.get_orderbook not implemented")

    @abstractmethod
    async def get_balances(self) -> Dict[str, Balance]:
        """Get account balances"""
        raise NotImplementedError(f"{self.__class__.__name__}.get_balances not implemented")

    @abstractmethod
    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal = None,
        client_order_id: str = None
    ) -> Order:
        """Create new order"""
        raise NotImplementedError(f"{self.__class__.__name__}.create_order not implemented")

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel order"""
        raise NotImplementedError(f"{self.__class__.__name__}.cancel_order not implemented")

    @abstractmethod
    async def get_order(self, symbol: str, order_id: str) -> Order:
        """Get order status"""
        raise NotImplementedError(f"{self.__class__.__name__}.get_order not implemented")

    @abstractmethod
    async def get_open_orders(self, symbol: str = None) -> List[Order]:
        """Get open orders"""
        raise NotImplementedError(f"{self.__class__.__name__}.get_open_orders not implemented")

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Dict = None,
        data: Dict = None,
        signed: bool = False
    ) -> Dict:
        """Make API request with rate limiting and error handling"""
        await self.rate_limiter.acquire()
        await self._ensure_session()

        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(signed, params or data)

        try:
            async with self._session.request(
                method,
                url,
                params=params if method == "GET" else None,
                json=data if method != "GET" else None,
                headers=headers
            ) as resp:
                text = await resp.text()

                if resp.status >= 400:
                    logger.error(f"{self.name} API error {resp.status}: {text}")
                    raise ExchangeError(f"API error {resp.status}: {text}")

                return json.loads(text) if text else {}

        except aiohttp.ClientError as e:
            logger.error(f"{self.name} connection error: {e}")
            raise ExchangeError(f"Connection error: {e}")

    @abstractmethod
    def _get_headers(self, signed: bool, params: Dict = None) -> Dict:
        """Get request headers (with signature if needed)"""
        raise NotImplementedError(f"{self.__class__.__name__}._get_headers not implemented")
