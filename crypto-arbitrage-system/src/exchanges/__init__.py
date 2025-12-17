"""
Unified Exchange Integration Layer

Production-grade exchange connections with:
- Unified interface for all exchanges
- Rate limiting and retry logic
- Order management
- Real-time data streaming
- Error handling and recovery

Module Structure:
- enums.py: OrderSide, OrderType, OrderStatus
- models.py: Ticker, OrderBook, Balance, Order, Trade
- rate_limiter.py: RateLimiter
- exceptions.py: ExchangeError
- base.py: BaseExchange
- binance.py: BinanceExchange
- mexc.py: MEXCExchange
- kucoin.py: KuCoinExchange
- manager.py: ExchangeManager
"""

# Import from submodules for backward compatibility
from .enums import OrderSide, OrderType, OrderStatus
from .models import Ticker, OrderBook, Balance, Order, Trade
from .rate_limiter import RateLimiter
from .exceptions import ExchangeError
from .base import BaseExchange
from .binance import BinanceExchange
from .mexc import MEXCExchange
from .kucoin import KuCoinExchange
from .manager import ExchangeManager


def create_exchange(
    name: str,
    api_key: str,
    api_secret: str,
    testnet: bool = False
) -> BaseExchange:
    """
    Create exchange instance by name
    """
    exchanges = {
        "binance": BinanceExchange,
        "mexc": MEXCExchange,
        "kucoin": KuCoinExchange
    }

    exchange_class = exchanges.get(name.lower())
    if not exchange_class:
        raise ValueError(f"Unknown exchange: {name}")

    return exchange_class(
        api_key=api_key,
        api_secret=api_secret,
        testnet=testnet
    )


__all__ = [
    # Enums
    "OrderSide",
    "OrderType",
    "OrderStatus",

    # Models
    "Ticker",
    "OrderBook",
    "Balance",
    "Order",
    "Trade",

    # Infrastructure
    "RateLimiter",
    "ExchangeError",

    # Base
    "BaseExchange",

    # Exchange implementations
    "BinanceExchange",
    "MEXCExchange",
    "KuCoinExchange",

    # Manager
    "ExchangeManager",

    # Factory
    "create_exchange",
]
