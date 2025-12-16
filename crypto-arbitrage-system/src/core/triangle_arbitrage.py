"""
Triangle Arbitrage Detection Engine

Detects triangular arbitrage opportunities across three trading pairs.

Example:
    BTC/USDT → ETH/BTC → ETH/USDT

    If 1 USDT can buy 0.000024 BTC, and 0.000024 BTC can buy 0.00056 ETH,
    and 0.00056 ETH sells for 1.01 USDT → profit of 1%

Key considerations:
- Trading fees on all three legs
- Slippage from order book depth
- Execution timing (all legs must complete quickly)
- Capital efficiency (need balances in starting currency)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from enum import Enum
from typing import Dict, List, Optional, Tuple, Set
import itertools

logger = logging.getLogger(__name__)


class TriangleDirection(Enum):
    """Direction of triangle arbitrage"""
    CLOCKWISE = "clockwise"        # A→B→C→A
    COUNTER_CLOCKWISE = "counter"  # A→C→B→A


@dataclass
class TradeLeg:
    """Single leg of a triangle arbitrage"""
    pair: str           # e.g., "BTC/USDT"
    base: str           # e.g., "BTC"
    quote: str          # e.g., "USDT"
    side: str           # "buy" or "sell"
    price: Decimal      # Execution price
    amount: Decimal     # Amount to trade
    fee_rate: Decimal   # Fee rate (e.g., 0.001 for 0.1%)
    exchange: str       # Exchange name


@dataclass
class TriangleOpportunity:
    """A detected triangle arbitrage opportunity"""
    id: str
    exchange: str
    base_currency: str      # Starting/ending currency (e.g., USDT)
    intermediate_a: str     # First intermediate (e.g., BTC)
    intermediate_b: str     # Second intermediate (e.g., ETH)
    direction: TriangleDirection

    # The three legs
    leg1: TradeLeg
    leg2: TradeLeg
    leg3: TradeLeg

    # Profitability
    starting_amount: Decimal
    ending_amount: Decimal
    gross_profit_pct: Decimal
    net_profit_pct: Decimal
    total_fees: Decimal

    # Timing
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Execution constraints
    max_executable_size: Decimal = Decimal("0")
    estimated_slippage_pct: Decimal = Decimal("0")
    confidence: float = 0.0

    @property
    def is_profitable(self) -> bool:
        return self.net_profit_pct > 0

    @property
    def net_profit_usd(self) -> Decimal:
        return self.starting_amount * self.net_profit_pct / 100

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "exchange": self.exchange,
            "path": f"{self.base_currency}→{self.intermediate_a}→{self.intermediate_b}→{self.base_currency}",
            "direction": self.direction.value,
            "gross_profit_pct": float(self.gross_profit_pct),
            "net_profit_pct": float(self.net_profit_pct),
            "total_fees": float(self.total_fees),
            "starting_amount": float(self.starting_amount),
            "max_executable": float(self.max_executable_size),
            "confidence": self.confidence,
            "detected_at": self.detected_at.isoformat()
        }


@dataclass
class OrderBookSnapshot:
    """Simplified order book for triangle calculations"""
    pair: str
    bids: List[Tuple[Decimal, Decimal]]  # [(price, quantity), ...]
    asks: List[Tuple[Decimal, Decimal]]
    timestamp: datetime

    @property
    def best_bid(self) -> Tuple[Decimal, Decimal]:
        return self.bids[0] if self.bids else (Decimal("0"), Decimal("0"))

    @property
    def best_ask(self) -> Tuple[Decimal, Decimal]:
        return self.asks[0] if self.asks else (Decimal("0"), Decimal("0"))

    @property
    def mid_price(self) -> Decimal:
        bid = self.best_bid[0]
        ask = self.best_ask[0]
        if bid == 0 or ask == 0:
            return Decimal("0")
        return (bid + ask) / 2


class TriangleArbitrageEngine:
    """
    Engine for detecting and analyzing triangle arbitrage opportunities.

    Usage:
        engine = TriangleArbitrageEngine(
            base_currencies=["USDT", "USDC"],
            min_profit_pct=0.1,
            fee_rate=0.001
        )

        # Update order books
        engine.update_orderbook("binance", "BTC/USDT", bids, asks)
        engine.update_orderbook("binance", "ETH/BTC", bids, asks)
        engine.update_orderbook("binance", "ETH/USDT", bids, asks)

        # Find opportunities
        opportunities = await engine.find_opportunities("binance")
    """

    def __init__(
        self,
        base_currencies: List[str] = None,
        min_profit_pct: Decimal = Decimal("0.1"),
        fee_rate: Decimal = Decimal("0.001"),
        min_trade_size_usd: Decimal = Decimal("100"),
        max_trade_size_usd: Decimal = Decimal("10000")
    ):
        """
        Initialize triangle arbitrage engine.

        Args:
            base_currencies: Currencies to use as starting point (e.g., ["USDT"])
            min_profit_pct: Minimum net profit percentage to report
            fee_rate: Trading fee rate per leg
            min_trade_size_usd: Minimum trade size in USD
            max_trade_size_usd: Maximum trade size in USD
        """
        self.base_currencies = set(base_currencies or ["USDT", "USDC", "BUSD"])
        self.min_profit_pct = min_profit_pct
        self.fee_rate = fee_rate
        self.min_trade_size_usd = min_trade_size_usd
        self.max_trade_size_usd = max_trade_size_usd

        # Order book storage: {exchange: {pair: OrderBookSnapshot}}
        self._orderbooks: Dict[str, Dict[str, OrderBookSnapshot]] = {}

        # Triangle cache: {exchange: [list of valid triangles]}
        self._triangle_cache: Dict[str, List[Tuple[str, str, str]]] = {}

        # Statistics
        self._stats = {
            "opportunities_found": 0,
            "profitable_opportunities": 0,
            "total_scans": 0
        }

        # Opportunity counter for IDs
        self._opportunity_counter = 0

    def update_orderbook(
        self,
        exchange: str,
        pair: str,
        bids: List[Tuple[Decimal, Decimal]],
        asks: List[Tuple[Decimal, Decimal]]
    ):
        """
        Update order book for a trading pair.

        Args:
            exchange: Exchange name
            pair: Trading pair (e.g., "BTC/USDT")
            bids: List of (price, quantity) tuples, best first
            asks: List of (price, quantity) tuples, best first
        """
        if exchange not in self._orderbooks:
            self._orderbooks[exchange] = {}

        self._orderbooks[exchange][pair] = OrderBookSnapshot(
            pair=pair,
            bids=bids,
            asks=asks,
            timestamp=datetime.now(timezone.utc)
        )

        # Invalidate triangle cache for this exchange
        if exchange in self._triangle_cache:
            del self._triangle_cache[exchange]

    def _find_valid_triangles(self, exchange: str) -> List[Tuple[str, str, str]]:
        """
        Find all valid triangle combinations for an exchange.

        A valid triangle is three pairs that form a loop:
        - Base/A, A/B, B/Base (or Base/B)

        Returns:
            List of (pair1, pair2, pair3) tuples
        """
        if exchange in self._triangle_cache:
            return self._triangle_cache[exchange]

        orderbooks = self._orderbooks.get(exchange, {})
        pairs = list(orderbooks.keys())

        # Parse pairs into base/quote
        pair_info = {}
        for pair in pairs:
            parts = pair.split("/")
            if len(parts) == 2:
                pair_info[pair] = (parts[0], parts[1])

        # Build currency graph
        currency_pairs: Dict[str, Set[str]] = {}  # currency -> set of connected currencies
        for pair, (base, quote) in pair_info.items():
            if base not in currency_pairs:
                currency_pairs[base] = set()
            if quote not in currency_pairs:
                currency_pairs[quote] = set()
            currency_pairs[base].add(quote)
            currency_pairs[quote].add(base)

        # Find triangles starting from base currencies
        triangles = []

        for base_currency in self.base_currencies:
            if base_currency not in currency_pairs:
                continue

            # Get currencies connected to base
            first_connections = currency_pairs.get(base_currency, set())

            for currency_a in first_connections:
                if currency_a in self.base_currencies:
                    continue  # Skip direct base-to-base

                # Get currencies connected to A
                second_connections = currency_pairs.get(currency_a, set())

                for currency_b in second_connections:
                    if currency_b == base_currency:
                        continue  # Can't go directly back
                    if currency_b == currency_a:
                        continue  # Can't loop to self

                    # Check if B connects back to base
                    if base_currency in currency_pairs.get(currency_b, set()):
                        # Found a valid triangle!
                        triangle = (base_currency, currency_a, currency_b)
                        if triangle not in triangles:
                            triangles.append(triangle)

        self._triangle_cache[exchange] = triangles
        logger.debug(f"Found {len(triangles)} valid triangles on {exchange}")

        return triangles

    def _get_pair_for_trade(
        self,
        exchange: str,
        currency_from: str,
        currency_to: str
    ) -> Optional[Tuple[str, str]]:
        """
        Find the pair and side for trading from one currency to another.

        Args:
            exchange: Exchange name
            currency_from: Currency we have
            currency_to: Currency we want

        Returns:
            (pair, side) or None if no pair exists
        """
        orderbooks = self._orderbooks.get(exchange, {})

        # Check direct pair: from/to (we would sell)
        direct_pair = f"{currency_from}/{currency_to}"
        if direct_pair in orderbooks:
            return (direct_pair, "sell")

        # Check reverse pair: to/from (we would buy)
        reverse_pair = f"{currency_to}/{currency_from}"
        if reverse_pair in orderbooks:
            return (reverse_pair, "buy")

        return None

    def _calculate_triangle_profit(
        self,
        exchange: str,
        base: str,
        intermediate_a: str,
        intermediate_b: str,
        starting_amount: Decimal
    ) -> Optional[TriangleOpportunity]:
        """
        Calculate profit for a specific triangle path.

        Path: base → intermediate_a → intermediate_b → base

        Args:
            exchange: Exchange name
            base: Starting currency (e.g., USDT)
            intermediate_a: First intermediate (e.g., BTC)
            intermediate_b: Second intermediate (e.g., ETH)
            starting_amount: Amount to start with

        Returns:
            TriangleOpportunity if valid, None otherwise
        """
        orderbooks = self._orderbooks.get(exchange, {})

        # Leg 1: base → intermediate_a
        leg1_info = self._get_pair_for_trade(exchange, base, intermediate_a)
        if not leg1_info:
            return None
        leg1_pair, leg1_side = leg1_info
        leg1_book = orderbooks.get(leg1_pair)
        if not leg1_book:
            return None

        # Leg 2: intermediate_a → intermediate_b
        leg2_info = self._get_pair_for_trade(exchange, intermediate_a, intermediate_b)
        if not leg2_info:
            return None
        leg2_pair, leg2_side = leg2_info
        leg2_book = orderbooks.get(leg2_pair)
        if not leg2_book:
            return None

        # Leg 3: intermediate_b → base
        leg3_info = self._get_pair_for_trade(exchange, intermediate_b, base)
        if not leg3_info:
            return None
        leg3_pair, leg3_side = leg3_info
        leg3_book = orderbooks.get(leg3_pair)
        if not leg3_book:
            return None

        # Calculate amounts through the triangle
        try:
            # Leg 1: Convert base → intermediate_a
            if leg1_side == "buy":
                # Buying intermediate_a with base
                leg1_price = leg1_book.best_ask[0]
                leg1_amount = starting_amount / leg1_price
            else:
                # Selling base for intermediate_a
                leg1_price = leg1_book.best_bid[0]
                leg1_amount = starting_amount * leg1_price

            # Apply fee
            leg1_fee = leg1_amount * self.fee_rate
            amount_after_leg1 = leg1_amount - leg1_fee

            # Leg 2: Convert intermediate_a → intermediate_b
            if leg2_side == "buy":
                leg2_price = leg2_book.best_ask[0]
                leg2_amount = amount_after_leg1 / leg2_price
            else:
                leg2_price = leg2_book.best_bid[0]
                leg2_amount = amount_after_leg1 * leg2_price

            # Apply fee
            leg2_fee = leg2_amount * self.fee_rate
            amount_after_leg2 = leg2_amount - leg2_fee

            # Leg 3: Convert intermediate_b → base
            if leg3_side == "buy":
                leg3_price = leg3_book.best_ask[0]
                leg3_amount = amount_after_leg2 / leg3_price
            else:
                leg3_price = leg3_book.best_bid[0]
                leg3_amount = amount_after_leg2 * leg3_price

            # Apply fee
            leg3_fee = leg3_amount * self.fee_rate
            ending_amount = leg3_amount - leg3_fee

            # Calculate profits
            gross_profit = ending_amount - starting_amount
            gross_profit_pct = (gross_profit / starting_amount) * 100

            # Convert all fees to base currency for accurate total
            # leg1_fee is in intermediate_a, convert to base using leg1 price
            # leg2_fee is in intermediate_b, convert via leg2 and leg3 prices
            # leg3_fee is already in base currency
            try:
                if leg1_side == "buy":
                    # leg1_fee is in intermediate_a, convert to base: fee * price
                    leg1_fee_in_base = leg1_fee * leg1_price
                else:
                    # leg1_fee is in intermediate_a, convert to base: fee / price
                    leg1_fee_in_base = leg1_fee / leg1_price if leg1_price > 0 else Decimal("0")

                if leg2_side == "buy":
                    # leg2_fee is in intermediate_b
                    leg2_fee_in_b = leg2_fee
                else:
                    leg2_fee_in_b = leg2_fee

                # Convert leg2_fee from intermediate_b to base using leg3 price
                if leg3_side == "buy":
                    leg2_fee_in_base = leg2_fee_in_b / leg3_price if leg3_price > 0 else Decimal("0")
                else:
                    leg2_fee_in_base = leg2_fee_in_b * leg3_price

                # leg3_fee is already in base currency
                leg3_fee_in_base = leg3_fee

                total_fees_in_base = leg1_fee_in_base + leg2_fee_in_base + leg3_fee_in_base
            except (ZeroDivisionError, InvalidOperation):
                # Fallback to simple sum if conversion fails
                total_fees_in_base = leg3_fee  # At least count the final leg fee

            net_profit = ending_amount - starting_amount
            net_profit_pct = (net_profit / starting_amount) * 100

            # Calculate max executable size based on order book depth
            max_size = self._calculate_max_executable_size(
                leg1_book, leg2_book, leg3_book,
                leg1_side, leg2_side, leg3_side
            )

            # Generate opportunity ID
            self._opportunity_counter += 1
            opp_id = f"tri_{exchange}_{self._opportunity_counter}"

            # Parse pair info for legs
            leg1_parts = leg1_pair.split("/")
            leg2_parts = leg2_pair.split("/")
            leg3_parts = leg3_pair.split("/")

            return TriangleOpportunity(
                id=opp_id,
                exchange=exchange,
                base_currency=base,
                intermediate_a=intermediate_a,
                intermediate_b=intermediate_b,
                direction=TriangleDirection.CLOCKWISE,
                leg1=TradeLeg(
                    pair=leg1_pair,
                    base=leg1_parts[0],
                    quote=leg1_parts[1],
                    side=leg1_side,
                    price=leg1_price,
                    amount=starting_amount if leg1_side == "buy" else leg1_amount,
                    fee_rate=self.fee_rate,
                    exchange=exchange
                ),
                leg2=TradeLeg(
                    pair=leg2_pair,
                    base=leg2_parts[0],
                    quote=leg2_parts[1],
                    side=leg2_side,
                    price=leg2_price,
                    amount=amount_after_leg1,
                    fee_rate=self.fee_rate,
                    exchange=exchange
                ),
                leg3=TradeLeg(
                    pair=leg3_pair,
                    base=leg3_parts[0],
                    quote=leg3_parts[1],
                    side=leg3_side,
                    price=leg3_price,
                    amount=amount_after_leg2,
                    fee_rate=self.fee_rate,
                    exchange=exchange
                ),
                starting_amount=starting_amount,
                ending_amount=ending_amount,
                gross_profit_pct=gross_profit_pct,
                net_profit_pct=net_profit_pct,
                total_fees=total_fees_in_base,
                max_executable_size=max_size,
                confidence=self._calculate_confidence(
                    net_profit_pct, max_size, leg1_book, leg2_book, leg3_book
                )
            )

        except (ZeroDivisionError, InvalidOperation):
            return None
        except Exception as e:
            logger.debug(f"Error calculating triangle {base}→{intermediate_a}→{intermediate_b}: {e}")
            return None

    def _calculate_max_executable_size(
        self,
        book1: OrderBookSnapshot,
        book2: OrderBookSnapshot,
        book3: OrderBookSnapshot,
        side1: str,
        side2: str,
        side3: str
    ) -> Decimal:
        """Calculate maximum executable size based on order book depth."""
        # Get available liquidity at best price
        if side1 == "buy":
            liq1 = book1.best_ask[1] * book1.best_ask[0]  # Quantity * price
        else:
            liq1 = book1.best_bid[1] * book1.best_bid[0]

        if side2 == "buy":
            liq2 = book2.best_ask[1] * book2.best_ask[0]
        else:
            liq2 = book2.best_bid[1] * book2.best_bid[0]

        if side3 == "buy":
            liq3 = book3.best_ask[1] * book3.best_ask[0]
        else:
            liq3 = book3.best_bid[1] * book3.best_bid[0]

        # Minimum across all legs
        return min(liq1, liq2, liq3, self.max_trade_size_usd)

    def _calculate_confidence(
        self,
        profit_pct: Decimal,
        max_size: Decimal,
        book1: OrderBookSnapshot,
        book2: OrderBookSnapshot,
        book3: OrderBookSnapshot
    ) -> float:
        """Calculate confidence score for the opportunity."""
        confidence = 0.5  # Base confidence

        # Higher profit → higher confidence
        if profit_pct > Decimal("0.5"):
            confidence += 0.2
        elif profit_pct > Decimal("0.2"):
            confidence += 0.1

        # Larger executable size → higher confidence
        if max_size > Decimal("5000"):
            confidence += 0.15
        elif max_size > Decimal("1000"):
            confidence += 0.1

        # Check order book freshness (all within 5 seconds)
        now = datetime.now(timezone.utc)
        max_age = max(
            (now - book1.timestamp).total_seconds(),
            (now - book2.timestamp).total_seconds(),
            (now - book3.timestamp).total_seconds()
        )

        if max_age < 1:
            confidence += 0.15
        elif max_age < 5:
            confidence += 0.05
        else:
            confidence -= 0.1  # Stale data penalty

        return min(max(confidence, 0.0), 1.0)

    async def find_opportunities(
        self,
        exchange: str,
        starting_amount: Decimal = None
    ) -> List[TriangleOpportunity]:
        """
        Find all triangle arbitrage opportunities on an exchange.

        Args:
            exchange: Exchange name
            starting_amount: Amount to simulate (defaults to min_trade_size_usd)

        Returns:
            List of profitable opportunities, sorted by profit
        """
        self._stats["total_scans"] += 1

        if starting_amount is None:
            starting_amount = self.min_trade_size_usd

        triangles = self._find_valid_triangles(exchange)
        opportunities = []

        for base, intermediate_a, intermediate_b in triangles:
            # Try clockwise direction
            opp = self._calculate_triangle_profit(
                exchange, base, intermediate_a, intermediate_b, starting_amount
            )

            if opp and opp.net_profit_pct >= self.min_profit_pct:
                opportunities.append(opp)
                self._stats["opportunities_found"] += 1
                if opp.is_profitable:
                    self._stats["profitable_opportunities"] += 1

            # Try counter-clockwise direction
            opp_reverse = self._calculate_triangle_profit(
                exchange, base, intermediate_b, intermediate_a, starting_amount
            )

            if opp_reverse and opp_reverse.net_profit_pct >= self.min_profit_pct:
                opp_reverse.direction = TriangleDirection.COUNTER_CLOCKWISE
                opportunities.append(opp_reverse)
                self._stats["opportunities_found"] += 1
                if opp_reverse.is_profitable:
                    self._stats["profitable_opportunities"] += 1

        # Sort by net profit, descending
        opportunities.sort(key=lambda x: x.net_profit_pct, reverse=True)

        return opportunities

    async def find_best_opportunity(
        self,
        exchange: str,
        starting_amount: Decimal = None
    ) -> Optional[TriangleOpportunity]:
        """
        Find the best triangle arbitrage opportunity.

        Args:
            exchange: Exchange name
            starting_amount: Amount to simulate

        Returns:
            Best opportunity or None
        """
        opportunities = await self.find_opportunities(exchange, starting_amount)
        return opportunities[0] if opportunities else None

    def get_stats(self) -> Dict:
        """Get engine statistics."""
        return dict(self._stats)

    def get_active_triangles(self, exchange: str) -> List[str]:
        """Get list of active triangle paths for an exchange."""
        triangles = self._find_valid_triangles(exchange)
        return [
            f"{base}→{a}→{b}→{base}"
            for base, a, b in triangles
        ]


# Convenience function for quick scans
async def scan_triangle_opportunities(
    exchange_name: str,
    orderbooks: Dict[str, Dict],
    min_profit_pct: Decimal = Decimal("0.1"),
    fee_rate: Decimal = Decimal("0.001")
) -> List[TriangleOpportunity]:
    """
    Quick scan for triangle opportunities.

    Args:
        exchange_name: Exchange identifier
        orderbooks: Dict of {pair: {"bids": [...], "asks": [...]}}
        min_profit_pct: Minimum profit to report
        fee_rate: Trading fee per leg

    Returns:
        List of opportunities
    """
    engine = TriangleArbitrageEngine(
        min_profit_pct=min_profit_pct,
        fee_rate=fee_rate
    )

    for pair, book in orderbooks.items():
        bids = [(Decimal(str(p)), Decimal(str(q))) for p, q in book.get("bids", [])]
        asks = [(Decimal(str(p)), Decimal(str(q))) for p, q in book.get("asks", [])]
        engine.update_orderbook(exchange_name, pair, bids, asks)

    return await engine.find_opportunities(exchange_name)


# Handle Decimal import for InvalidOperation
try:
    from decimal import InvalidOperation
except ImportError:
    InvalidOperation = Exception
