"""
Exchange Manager

Manages multiple exchange connections with unified interface.
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional

from .base import BaseExchange
from .enums import OrderSide

logger = logging.getLogger(__name__)


class ExchangeManager:
    """
    Manages multiple exchange connections

    Features:
    - Unified interface across exchanges
    - Automatic failover
    - Aggregated order book
    - Best price routing
    """

    def __init__(self):
        self._exchanges: Dict[str, BaseExchange] = {}

    def add_exchange(self, exchange: BaseExchange):
        """Add exchange to manager"""
        self._exchanges[exchange.name] = exchange
        logger.info(f"Added exchange: {exchange.name}")

    def get_exchange(self, name: str) -> Optional[BaseExchange]:
        """Get exchange by name"""
        return self._exchanges.get(name)

    async def close_all(self):
        """Close all exchange connections"""
        for exchange in self._exchanges.values():
            await exchange.close()

    async def get_best_price(
        self,
        symbol: str,
        side: OrderSide,
        quantity: Decimal = None
    ) -> Dict:
        """
        Find best price across all exchanges

        Returns exchange name and price
        """
        best = {"exchange": None, "price": None}

        for name, exchange in self._exchanges.items():
            try:
                orderbook = await exchange.get_orderbook(symbol)

                if side == OrderSide.BUY:
                    # Best ask (lowest)
                    if orderbook.asks:
                        price = orderbook.asks[0][0]
                        if best["price"] is None or price < best["price"]:
                            best = {"exchange": name, "price": price}
                else:
                    # Best bid (highest)
                    if orderbook.bids:
                        price = orderbook.bids[0][0]
                        if best["price"] is None or price > best["price"]:
                            best = {"exchange": name, "price": price}

            except Exception as e:
                logger.warning(f"Error getting price from {name}: {e}")

        return best

    async def get_arbitrage_opportunities(self, symbol: str) -> List[Dict]:
        """
        Find arbitrage opportunities across exchanges

        Returns list of opportunities with expected profit
        """
        opportunities = []
        prices = {}

        # Collect prices from all exchanges
        for name, exchange in self._exchanges.items():
            try:
                orderbook = await exchange.get_orderbook(symbol)
                prices[name] = {
                    "bid": orderbook.bids[0][0] if orderbook.bids else None,
                    "ask": orderbook.asks[0][0] if orderbook.asks else None,
                    "bid_qty": orderbook.bids[0][1] if orderbook.bids else None,
                    "ask_qty": orderbook.asks[0][1] if orderbook.asks else None
                }
            except Exception as e:
                logger.warning(f"Error getting orderbook from {name}: {e}")

        # Find opportunities
        exchanges = list(prices.keys())
        for i, buy_ex in enumerate(exchanges):
            for sell_ex in exchanges[i + 1:]:
                buy_price = prices[buy_ex].get("ask")
                sell_price = prices[sell_ex].get("bid")

                if buy_price and sell_price and sell_price > buy_price:
                    spread = (sell_price - buy_price) / buy_price * 100
                    opportunities.append({
                        "buy_exchange": buy_ex,
                        "sell_exchange": sell_ex,
                        "buy_price": buy_price,
                        "sell_price": sell_price,
                        "spread_percent": float(spread),
                        "max_quantity": min(
                            prices[buy_ex].get("ask_qty", Decimal("0")),
                            prices[sell_ex].get("bid_qty", Decimal("0"))
                        )
                    })

                # Check reverse direction
                buy_price = prices[sell_ex].get("ask")
                sell_price = prices[buy_ex].get("bid")

                if buy_price and sell_price and sell_price > buy_price:
                    spread = (sell_price - buy_price) / buy_price * 100
                    opportunities.append({
                        "buy_exchange": sell_ex,
                        "sell_exchange": buy_ex,
                        "buy_price": buy_price,
                        "sell_price": sell_price,
                        "spread_percent": float(spread),
                        "max_quantity": min(
                            prices[sell_ex].get("ask_qty", Decimal("0")),
                            prices[buy_ex].get("bid_qty", Decimal("0"))
                        )
                    })

        # Sort by spread
        opportunities.sort(key=lambda x: x["spread_percent"], reverse=True)
        return opportunities
