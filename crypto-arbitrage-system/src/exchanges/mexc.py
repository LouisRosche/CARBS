"""
MEXC Exchange

MEXC spot trading implementation.
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


class MEXCExchange(BaseExchange):
    """
    MEXC exchange implementation

    Notable: 0% maker fees!
    """

    @property
    def name(self) -> str:
        return "mexc"

    @property
    def base_url(self) -> str:
        return "https://api.mexc.com"

    def _get_headers(self, signed: bool, params: Dict = None) -> Dict:
        headers = {
            "X-MEXC-APIKEY": self.api_key,
            "Content-Type": "application/json"
        }
        return headers

    def _sign_params(self, params: Dict) -> Dict:
        """Add signature to params"""
        params = params or {}
        params["timestamp"] = int(time.time() * 1000)

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
            bid=Decimal(data.get("bidPrice", "0")),
            ask=Decimal(data.get("askPrice", "0")),
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
            bids=[(Decimal(p), Decimal(q)) for p, q in data.get("bids", [])],
            asks=[(Decimal(p), Decimal(q)) for p, q in data.get("asks", [])],
            timestamp=datetime.now(timezone.utc)
        )

    async def get_balances(self) -> Dict[str, Balance]:
        """Get account balances"""
        params = self._sign_params({})
        data = await self._request("GET", "/api/v3/account", params, signed=True)

        balances = {}
        for b in data.get("balances", []):
            free = Decimal(b.get("free", "0"))
            locked = Decimal(b.get("locked", "0"))
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
            "type": "LIMIT" if order_type == OrderType.LIMIT else "MARKET",
            "quantity": str(quantity)
        }

        if order_type == OrderType.LIMIT and price:
            params["price"] = str(price)

        if client_order_id:
            params["newClientOrderId"] = client_order_id

        params = self._sign_params(params)
        data = await self._request("POST", "/api/v3/order", data=params, signed=True)

        return Order(
            order_id=str(data.get("orderId", "")),
            client_order_id=data.get("clientOrderId", ""),
            symbol=symbol,
            side=side,
            order_type=order_type,
            status=OrderStatus.OPEN,
            price=price or Decimal("0"),
            quantity=quantity,
            created_at=datetime.now(timezone.utc)
        )

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

        return Order(
            order_id=str(data.get("orderId", "")),
            client_order_id=data.get("clientOrderId", ""),
            symbol=symbol,
            side=OrderSide.BUY if data.get("side") == "BUY" else OrderSide.SELL,
            order_type=OrderType.LIMIT,
            status=OrderStatus.OPEN,
            price=Decimal(data.get("price", "0")),
            quantity=Decimal(data.get("origQty", "0")),
            filled_quantity=Decimal(data.get("executedQty", "0"))
        )

    async def get_open_orders(self, symbol: str = None) -> List[Order]:
        """Get open orders"""
        params = {}
        if symbol:
            params["symbol"] = symbol

        params = self._sign_params(params)
        data = await self._request("GET", "/api/v3/openOrders", params, signed=True)

        return [
            Order(
                order_id=str(o.get("orderId", "")),
                client_order_id=o.get("clientOrderId", ""),
                symbol=o["symbol"],
                side=OrderSide.BUY if o.get("side") == "BUY" else OrderSide.SELL,
                order_type=OrderType.LIMIT,
                status=OrderStatus.OPEN,
                price=Decimal(o.get("price", "0")),
                quantity=Decimal(o.get("origQty", "0"))
            )
            for o in data
        ]
