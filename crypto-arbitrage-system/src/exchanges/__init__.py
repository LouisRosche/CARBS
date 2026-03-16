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
"""

# Import from submodules for backward compatibility
from .enums import OrderSide, OrderType, OrderStatus
from .models import Ticker, OrderBook, Balance, Order, Trade
from .rate_limiter import RateLimiter
from .exceptions import ExchangeError


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
]
