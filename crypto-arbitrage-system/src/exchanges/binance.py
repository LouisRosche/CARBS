"""
Binance Exchange

Binance spot trading implementation.
"""

import hashlib
import hmac
import time
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List

from .base import BaseExchange
from .enums import OrderSide, OrderType, OrderStatus
from .models import Ticker, OrderBook, Balance, Order
from .exceptions import ExchangeError

logger = logging.getLogger(__name__)


class BinanceExchange(BaseExchange):
    """
    Binance exchange implementation

    Supports:
    - Spot trading
    - Real-time websockets
    - All order types
    """

    @property
    def name(self) -> str:
        return "binance"

    @property
    def base_url(self) -> str:
        if self.testnet:
            return "https://testnet.binance.vision"
        return "https://api.binance.com"

    def _get_headers(self, signed: bool, params: Dict = None) -> Dict:
        headers = {"X-MBX-APIKEY": self.api_key}
        return headers

    def _sign_params(self, params: Dict) -> Dict:
        """Add signature to params"""
        params = params or {}
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 5000

        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()

        params["signature"] = signature
        return params

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get 24h ticker"""
        data = await self._request("GET", "/api/v3/ticker/24hr", {"symbol": symbol})

        return Ticker(
            symbol=data["symbol"],
            bid=Decimal(data["bidPrice"]),
            ask=Decimal(data["askPrice"]),
            last=Decimal(data["lastPrice"]),
            volume_24h=Decimal(data["volume"]),
            timestamp=datetime.now(timezone.utc)
        )

    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """Get order book"""
        data = await self._request("GET", "/api/v3/depth", {
            "symbol": symbol,
            "limit": depth
        })

        return OrderBook(
            symbol=symbol,
            bids=[(Decimal(p), Decimal(q)) for p, q in data["bids"]],
            asks=[(Decimal(p), Decimal(q)) for p, q in data["asks"]],
            timestamp=datetime.now(timezone.utc)
        )

    async def get_balances(self) -> Dict[str, Balance]:
        """Get account balances"""
        params = self._sign_params({})
        data = await self._request("GET", "/api/v3/account", params, signed=True)

        balances = {}
        for b in data.get("balances", []):
            free = Decimal(b["free"])
            locked = Decimal(b["locked"])
            if free > 0 or locked > 0:
                balances[b["asset"]] = Balance(
                    asset=b["asset"],
                    free=free,
                    locked=locked
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
        """Create new order"""
        params = {
            "symbol": symbol,
            "side": side.value.upper(),
            "type": self._map_order_type(order_type),
            "quantity": str(quantity)
        }

        if order_type == OrderType.LIMIT:
            params["timeInForce"] = "GTC"
            params["price"] = str(price)

        if client_order_id:
            params["newClientOrderId"] = client_order_id

        params = self._sign_params(params)
        data = await self._request("POST", "/api/v3/order", data=params, signed=True)

        return self._parse_order(data)

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel order"""
        params = self._sign_params({
            "symbol": symbol,
            "orderId": order_id
        })

        try:
            await self._request("DELETE", "/api/v3/order", params, signed=True)
            return True
        except ExchangeError:
            return False

    async def get_order(self, symbol: str, order_id: str) -> Order:
        """Get order status"""
        params = self._sign_params({
            "symbol": symbol,
            "orderId": order_id
        })

        data = await self._request("GET", "/api/v3/order", params, signed=True)
        return self._parse_order(data)

    async def get_open_orders(self, symbol: str = None) -> List[Order]:
        """Get open orders"""
        params = {}
        if symbol:
            params["symbol"] = symbol

        params = self._sign_params(params)
        data = await self._request("GET", "/api/v3/openOrders", params, signed=True)

        return [self._parse_order(o) for o in data]

    def _map_order_type(self, order_type: OrderType) -> str:
        """Map order type to Binance format"""
        mapping = {
            OrderType.MARKET: "MARKET",
            OrderType.LIMIT: "LIMIT",
            OrderType.STOP_LOSS: "STOP_LOSS",
            OrderType.STOP_LIMIT: "STOP_LOSS_LIMIT",
            OrderType.TAKE_PROFIT: "TAKE_PROFIT"
        }
        return mapping.get(order_type, "LIMIT")

    def _parse_order(self, data: Dict) -> Order:
        """Parse order from API response"""
        status_map = {
            "NEW": OrderStatus.OPEN,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.EXPIRED
        }

        return Order(
            order_id=str(data["orderId"]),
            client_order_id=data.get("clientOrderId", ""),
            symbol=data["symbol"],
            side=OrderSide.BUY if data["side"] == "BUY" else OrderSide.SELL,
            order_type=OrderType.LIMIT,  # Simplified
            status=status_map.get(data["status"], OrderStatus.PENDING),
            price=Decimal(data.get("price", "0")),
            quantity=Decimal(data["origQty"]),
            filled_quantity=Decimal(data.get("executedQty", "0")),
            created_at=datetime.fromtimestamp(data["time"] / 1000, tz=timezone.utc) if "time" in data else None
        )
