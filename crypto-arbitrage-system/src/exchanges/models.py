"""
Exchange Models

Dataclasses for market data and order management.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List

from .enums import OrderSide, OrderType, OrderStatus


@dataclass
class Ticker:
    """Real-time ticker data"""
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume_24h: Decimal
    timestamp: datetime


@dataclass
class OrderBook:
    """Order book snapshot"""
    symbol: str
    bids: List[tuple]  # [(price, quantity), ...]
    asks: List[tuple]
    timestamp: datetime

    @property
    def spread(self) -> Decimal:
        if self.asks and self.bids:
            return self.asks[0][0] - self.bids[0][0]
        return Decimal("0")

    @property
    def spread_percent(self) -> Decimal:
        if self.asks and self.bids and self.bids[0][0] > 0:
            return (self.spread / self.bids[0][0]) * 100
        return Decimal("0")


@dataclass
class Balance:
    """Account balance for an asset"""
    asset: str
    free: Decimal
    locked: Decimal

    @property
    def total(self) -> Decimal:
        return self.free + self.locked


@dataclass
class Order:
    """Order details"""
    order_id: str
    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    status: OrderStatus
    price: Decimal
    quantity: Decimal
    filled_quantity: Decimal = Decimal("0")
    avg_fill_price: Decimal = None
    fee: Decimal = Decimal("0")
    fee_asset: str = ""
    created_at: datetime = None
    updated_at: datetime = None


@dataclass
class Trade:
    """Executed trade"""
    trade_id: str
    order_id: str
    symbol: str
    side: OrderSide
    price: Decimal
    quantity: Decimal
    fee: Decimal
    fee_asset: str
    timestamp: datetime
