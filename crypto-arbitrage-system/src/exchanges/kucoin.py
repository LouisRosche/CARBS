"""
KuCoin Exchange

KuCoin spot trading implementation.
"""

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List

import aiohttp

from .base import BaseExchange
from .enums import OrderSide, OrderType, OrderStatus
from .models import Ticker, OrderBook, Balance, Order
from .exceptions import ExchangeError

logger = logging.getLogger(__name__)


class KuCoinExchange(BaseExchange):
    """
    KuCoin exchange implementation

    Features:
    - Spot trading
    - Full order management
    - Real-time data
    - Sandbox/testnet support

    Note: KuCoin requires a passphrase in addition to API key/secret.
    Set via constructor or environment variable KUCOIN_PASSPHRASE.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        passphrase: str = None,
        testnet: bool = False,
        rate_limit: float = 10
    ):
        # CRITICAL COMPLIANCE CHECK: KuCoin is prohibited for US persons
        # CFTC and FinCEN enforcement actions filed in 2024
        # See docs/EXCHANGE_COMPLIANCE.md for full details
        user_jurisdiction = os.getenv('USER_JURISDICTION', '').upper()
        if user_jurisdiction == 'US':
            raise ExchangeError(
                "⚠️ REGULATORY VIOLATION: KuCoin is PROHIBITED for US persons.\n"
                "KuCoin faces active CFTC and FinCEN enforcement actions.\n"
                "Using KuCoin as a US person violates federal law.\n"
                "See docs/EXCHANGE_COMPLIANCE.md for compliant alternatives.\n"
                "Set USER_JURISDICTION environment variable to override this check."
            )

        # Log warning even if not US (regulatory risk exists globally)
        if not testnet:
            logger.warning(
                "⚠️ KuCoin Regulatory Risk: This exchange faces ongoing enforcement actions. "
                "Review docs/EXCHANGE_COMPLIANCE.md before using. "
                "Consider Binance or MEXC as safer alternatives."
            )

        super().__init__(api_key, api_secret, testnet, rate_limit)
        self.passphrase = passphrase or os.getenv('KUCOIN_PASSPHRASE', '')
        self._api_version = "v1"

    @property
    def name(self) -> str:
        return "kucoin"

    @property
    def base_url(self) -> str:
        if self.testnet:
            return "https://openapi-sandbox.kucoin.com"
        return "https://api.kucoin.com"

    def _convert_symbol(self, symbol: str) -> str:
        """Convert standard symbol (BTCUSDT) to KuCoin format (BTC-USDT)"""
        # Handle common pairs
        for quote in ['USDT', 'USDC', 'BTC', 'ETH', 'KCS']:
            if symbol.endswith(quote) and '-' not in symbol:
                base = symbol[:-len(quote)]
                return f"{base}-{quote}"
        return symbol

    def _reverse_symbol(self, kucoin_symbol: str) -> str:
        """Convert KuCoin symbol (BTC-USDT) back to standard format (BTCUSDT)"""
        return kucoin_symbol.replace('-', '')

    def _sign_request(self, timestamp: str, method: str, endpoint: str, body: str = '') -> str:
        """Generate KuCoin API signature"""
        str_to_sign = f"{timestamp}{method}{endpoint}{body}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            str_to_sign.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')

    def _sign_passphrase(self) -> str:
        """Sign the passphrase for API v2"""
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            self.passphrase.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')

    def _get_headers(self, signed: bool, params: Dict = None, method: str = "GET", endpoint: str = "") -> Dict:
        headers = {"Content-Type": "application/json"}

        if signed:
            timestamp = str(int(time.time() * 1000))
            body = json.dumps(params) if params and method != "GET" else ""

            headers["KC-API-KEY"] = self.api_key
            headers["KC-API-TIMESTAMP"] = timestamp
            headers["KC-API-SIGN"] = self._sign_request(timestamp, method, endpoint, body)
            headers["KC-API-PASSPHRASE"] = self._sign_passphrase()
            headers["KC-API-KEY-VERSION"] = "2"

        return headers

    async def _kucoin_request(
        self,
        method: str,
        endpoint: str,
        params: Dict = None,
        signed: bool = False
    ) -> Dict:
        """Make KuCoin API request with proper signing"""
        await self.rate_limiter.acquire()
        await self._ensure_session()

        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(signed, params, method, endpoint)

        try:
            if method == "GET":
                async with self._session.get(url, params=params, headers=headers) as resp:
                    data = await resp.json()
            elif method == "POST":
                async with self._session.post(url, json=params, headers=headers) as resp:
                    data = await resp.json()
            elif method == "DELETE":
                async with self._session.delete(url, params=params, headers=headers) as resp:
                    data = await resp.json()
            else:
                raise ExchangeError(f"Unsupported method: {method}")

            if data.get("code") != "200000":
                error_msg = data.get("msg", "Unknown error")
                logger.error(f"KuCoin API error: {error_msg}")
                raise ExchangeError(f"KuCoin API error: {error_msg}")

            return data.get("data", {})

        except aiohttp.ClientError as e:
            logger.error(f"KuCoin connection error: {e}")
            raise ExchangeError(f"Connection error: {e}")

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get ticker (KuCoin uses different symbol format: BTC-USDT)"""
        kucoin_symbol = self._convert_symbol(symbol)
        data = await self._kucoin_request("GET", "/api/v1/market/orderbook/level1", {
            "symbol": kucoin_symbol
        })

        return Ticker(
            symbol=symbol,
            bid=Decimal(data.get("bestBid", "0") or "0"),
            ask=Decimal(data.get("bestAsk", "0") or "0"),
            last=Decimal(data.get("price", "0") or "0"),
            volume_24h=Decimal(data.get("size", "0") or "0"),
            timestamp=datetime.fromtimestamp(
                int(data.get("time", time.time() * 1000)) / 1000,
                tz=timezone.utc
            )
        )

    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """Get order book"""
        kucoin_symbol = self._convert_symbol(symbol)
        endpoint = "/api/v1/market/orderbook/level2_20" if depth <= 20 else "/api/v1/market/orderbook/level2_100"

        data = await self._kucoin_request("GET", endpoint, {"symbol": kucoin_symbol})

        return OrderBook(
            symbol=symbol,
            bids=[(Decimal(p), Decimal(q)) for p, q in data.get("bids", [])],
            asks=[(Decimal(p), Decimal(q)) for p, q in data.get("asks", [])],
            timestamp=datetime.fromtimestamp(
                int(data.get("time", time.time() * 1000)) / 1000,
                tz=timezone.utc
            )
        )

    async def get_balances(self) -> Dict[str, Balance]:
        """Get account balances"""
        if not self.passphrase:
            logger.warning("KuCoin passphrase not set - cannot fetch balances")
            return {}

        data = await self._kucoin_request(
            "GET",
            "/api/v1/accounts",
            {"type": "trade"},
            signed=True
        )

        balances = {}
        for account in data if isinstance(data, list) else []:
            asset = account.get("currency", "")
            available = Decimal(account.get("available", "0"))
            holds = Decimal(account.get("holds", "0"))

            if available > 0 or holds > 0:
                if asset in balances:
                    # Aggregate across account types
                    balances[asset].free += available
                    balances[asset].locked += holds
                else:
                    balances[asset] = Balance(
                        asset=asset,
                        free=available,
                        locked=holds
                    )

        return balances

    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal = None,
        client_order_id: str = None
    ) -> Order:
        """Create new order on KuCoin"""
        if not self.passphrase:
            raise ExchangeError("KuCoin passphrase required for trading")

        kucoin_symbol = self._convert_symbol(symbol)

        # Generate client order ID if not provided
        if not client_order_id:
            client_order_id = str(uuid.uuid4())[:32]

        params = {
            "clientOid": client_order_id,
            "symbol": kucoin_symbol,
            "side": side.value.lower(),
            "type": "market" if order_type == OrderType.MARKET else "limit",
            "size": str(quantity)
        }

        if order_type == OrderType.LIMIT:
            if price is None:
                raise ExchangeError("Price required for limit orders")
            params["price"] = str(price)
            params["timeInForce"] = "GTC"

        data = await self._kucoin_request("POST", "/api/v1/orders", params, signed=True)

        return Order(
            order_id=data.get("orderId", ""),
            client_order_id=client_order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            status=OrderStatus.OPEN,
            price=price or Decimal("0"),
            quantity=quantity,
            created_at=datetime.now(timezone.utc)
        )

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel order by ID"""
        if not self.passphrase:
            raise ExchangeError("KuCoin passphrase required for trading")

        try:
            await self._kucoin_request(
                "DELETE",
                f"/api/v1/orders/{order_id}",
                signed=True
            )
            return True
        except ExchangeError as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def get_order(self, symbol: str, order_id: str) -> Order:
        """Get order status by ID"""
        if not self.passphrase:
            raise ExchangeError("KuCoin passphrase required")

        data = await self._kucoin_request(
            "GET",
            f"/api/v1/orders/{order_id}",
            signed=True
        )

        # Map KuCoin status to our status enum
        status_map = {
            "active": OrderStatus.OPEN,
            "done": OrderStatus.FILLED,
            "cancelled": OrderStatus.CANCELLED
        }

        kucoin_status = "active" if data.get("isActive") else "done"
        if data.get("cancelExist"):
            kucoin_status = "cancelled"

        return Order(
            order_id=data.get("id", order_id),
            client_order_id=data.get("clientOid", ""),
            symbol=self._reverse_symbol(data.get("symbol", symbol)),
            side=OrderSide.BUY if data.get("side") == "buy" else OrderSide.SELL,
            order_type=OrderType.MARKET if data.get("type") == "market" else OrderType.LIMIT,
            status=status_map.get(kucoin_status, OrderStatus.PENDING),
            price=Decimal(data.get("price", "0") or "0"),
            quantity=Decimal(data.get("size", "0")),
            filled_quantity=Decimal(data.get("dealSize", "0")),
            avg_fill_price=Decimal(data.get("dealFunds", "0")) / Decimal(data.get("dealSize", "1") or "1")
            if Decimal(data.get("dealSize", "0")) > 0 else None,
            fee=Decimal(data.get("fee", "0")),
            fee_asset=data.get("feeCurrency", ""),
            created_at=datetime.fromtimestamp(
                int(data.get("createdAt", time.time() * 1000)) / 1000,
                tz=timezone.utc
            )
        )

    async def get_open_orders(self, symbol: str = None) -> List[Order]:
        """Get all open orders"""
        if not self.passphrase:
            return []

        params = {"status": "active"}
        if symbol:
            params["symbol"] = self._convert_symbol(symbol)

        data = await self._kucoin_request(
            "GET",
            "/api/v1/orders",
            params,
            signed=True
        )

        orders = []
        items = data.get("items", []) if isinstance(data, dict) else []

        for item in items:
            orders.append(Order(
                order_id=item.get("id", ""),
                client_order_id=item.get("clientOid", ""),
                symbol=self._reverse_symbol(item.get("symbol", "")),
                side=OrderSide.BUY if item.get("side") == "buy" else OrderSide.SELL,
                order_type=OrderType.MARKET if item.get("type") == "market" else OrderType.LIMIT,
                status=OrderStatus.OPEN,
                price=Decimal(item.get("price", "0") or "0"),
                quantity=Decimal(item.get("size", "0")),
                filled_quantity=Decimal(item.get("dealSize", "0")),
                created_at=datetime.fromtimestamp(
                    int(item.get("createdAt", time.time() * 1000)) / 1000,
                    tz=timezone.utc
                )
            ))

        return orders
