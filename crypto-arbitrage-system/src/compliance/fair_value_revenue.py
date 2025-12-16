"""
Fair Value Measurement and Revenue Recognition Module

Implements GAAP standards:
- ASC 820: Fair Value Measurement
- ASC 606: Revenue from Contracts with Customers
- ASC 815: Derivatives and Hedging (if applicable)
- ASC 825: Financial Instruments

For cryptocurrency trading operations:
- Fair value hierarchy (Level 1, 2, 3)
- Observable vs. unobservable inputs
- Revenue recognition for trading activities
- Performance obligations
- Transaction price allocation
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class FairValueLevel(Enum):
    """
    ASC 820 Fair Value Hierarchy

    Level 1: Quoted prices in active markets for identical assets
    Level 2: Observable inputs other than Level 1 (e.g., quoted prices for similar assets)
    Level 3: Unobservable inputs (model-based valuations)
    """
    LEVEL_1 = "level_1"
    LEVEL_2 = "level_2"
    LEVEL_3 = "level_3"


class ValuationTechnique(Enum):
    """Valuation techniques per ASC 820"""
    MARKET_APPROACH = "market_approach"  # Prices from market transactions
    INCOME_APPROACH = "income_approach"  # Present value techniques
    COST_APPROACH = "cost_approach"      # Replacement cost


class RevenueCategory(Enum):
    """Revenue categories per ASC 606"""
    TRADING_REVENUE = "trading_revenue"
    REALIZED_GAINS = "realized_gains"
    UNREALIZED_GAINS = "unrealized_gains"  # Note: Not revenue under GAAP
    INTEREST_INCOME = "interest_income"
    STAKING_REWARDS = "staking_rewards"
    LENDING_INCOME = "lending_income"


@dataclass
class FairValueMeasurement:
    """
    Fair value measurement for an asset per ASC 820

    Records:
    - Asset identification
    - Fair value amount
    - Hierarchy level
    - Valuation technique
    - Key inputs
    - Measurement date
    """
    asset_id: str
    asset_type: str  # "BTC", "ETH", etc.
    fair_value: Decimal
    measurement_date: datetime

    # Hierarchy classification
    hierarchy_level: FairValueLevel

    # Valuation technique and inputs
    valuation_technique: ValuationTechnique
    principal_market: str  # Primary exchange used
    observable_inputs: Dict[str, any] = field(default_factory=dict)
    unobservable_inputs: Dict[str, any] = field(default_factory=dict)

    # Supporting data
    quoted_prices: List[Decimal] = field(default_factory=list)
    volume: Decimal = Decimal("0")
    bid_ask_spread: Decimal = Decimal("0")

    # Valuation uncertainty
    uncertainty_range_low: Optional[Decimal] = None
    uncertainty_range_high: Optional[Decimal] = None


@dataclass
class RevenueRecognitionEvent:
    """
    Revenue recognition event per ASC 606

    Five-step model:
    1. Identify the contract
    2. Identify performance obligations
    3. Determine transaction price
    4. Allocate transaction price
    5. Recognize revenue when obligation satisfied
    """
    event_id: str
    recognition_date: datetime

    # Step 1: Contract identification
    contract_id: str
    contract_type: str  # "arbitrage_trade", "spot_trade", etc.

    # Step 2: Performance obligations
    performance_obligations: List[str] = field(default_factory=list)

    # Step 3: Transaction price
    transaction_price: Decimal = Decimal("0")
    variable_consideration: Decimal = Decimal("0")
    consideration_adjustments: Dict[str, Decimal] = field(default_factory=dict)

    # Step 4: Price allocation
    allocated_prices: Dict[str, Decimal] = field(default_factory=dict)

    # Step 5: Recognition
    revenue_recognized: Decimal = Decimal("0")
    revenue_category: RevenueCategory = RevenueCategory.TRADING_REVENUE

    # Supporting documentation
    supporting_docs: List[str] = field(default_factory=list)


class FairValueEngine:
    """
    Fair Value Measurement Engine per ASC 820

    Determines fair value for digital assets using:
    - Level 1: Quoted exchange prices (primary method for liquid assets)
    - Level 2: Adjusted quoted prices or similar assets
    - Level 3: Valuation models for illiquid assets
    """

    def __init__(self):
        self.measurements: List[FairValueMeasurement] = []

    async def measure_asset_fair_value(
        self,
        asset_type: str,
        quantity: Decimal,
        exchange_prices: Dict[str, Decimal],
        exchange_volumes: Dict[str, Decimal],
        measurement_date: datetime = None
    ) -> FairValueMeasurement:
        """
        Measure fair value of digital asset

        For liquid cryptocurrencies (BTC, ETH):
        - Uses Level 1 inputs (quoted prices from active exchanges)
        - Determines principal market (highest volume)
        - Calculates volume-weighted average price (VWAP)

        For illiquid or proprietary tokens:
        - May require Level 2 or Level 3 inputs
        """
        if measurement_date is None:
            measurement_date = datetime.now(timezone.utc)

        # Determine principal market (highest volume)
        principal_market = max(exchange_volumes.items(), key=lambda x: x[1])[0]
        principal_price = exchange_prices[principal_market]

        # Check if active market exists (ASC 820-10-35-54C)
        is_active_market = self._assess_market_activity(exchange_volumes)

        if is_active_market:
            # Level 1: Use quoted prices
            hierarchy_level = FairValueLevel.LEVEL_1
            valuation_technique = ValuationTechnique.MARKET_APPROACH

            # Calculate VWAP across exchanges for reasonableness check
            total_volume = sum(exchange_volumes.values())
            vwap = sum(
                price * exchange_volumes[exchange] / total_volume
                for exchange, price in exchange_prices.items()
            )

            fair_value = principal_price  # Per ASC 820, use principal market price

            # Calculate bid-ask spread as measure of liquidity
            prices = list(exchange_prices.values())
            bid_ask_spread = (max(prices) - min(prices)) / min(prices) * Decimal("100")

            measurement = FairValueMeasurement(
                asset_id=f"{asset_type}_{measurement_date.strftime('%Y%m%d')}",
                asset_type=asset_type,
                fair_value=fair_value,
                measurement_date=measurement_date,
                hierarchy_level=hierarchy_level,
                valuation_technique=valuation_technique,
                principal_market=principal_market,
                observable_inputs={
                    "quoted_prices": exchange_prices,
                    "trading_volumes": exchange_volumes,
                    "vwap": str(vwap)
                },
                quoted_prices=[Decimal(str(p)) for p in exchange_prices.values()],
                volume=total_volume,
                bid_ask_spread=bid_ask_spread
            )

        else:
            # Inactive market - may require Level 2 or Level 3
            hierarchy_level = FairValueLevel.LEVEL_2
            valuation_technique = ValuationTechnique.MARKET_APPROACH

            # Use adjusted prices or prices of similar assets
            fair_value = self._calculate_adjusted_fair_value(
                asset_type, exchange_prices, exchange_volumes
            )

            measurement = FairValueMeasurement(
                asset_id=f"{asset_type}_{measurement_date.strftime('%Y%m%d')}",
                asset_type=asset_type,
                fair_value=fair_value,
                measurement_date=measurement_date,
                hierarchy_level=hierarchy_level,
                valuation_technique=valuation_technique,
                principal_market=principal_market,
                observable_inputs={
                    "quoted_prices": exchange_prices,
                    "adjustment_factors": {"illiquidity_discount": "5%"}
                },
                unobservable_inputs={
                    "market_activity_assessment": "low"
                }
            )

        self.measurements.append(measurement)

        logger.info(
            f"Fair value measured for {asset_type}: ${fair_value:.2f} "
            f"({hierarchy_level.value}, {principal_market})"
        )

        return measurement

    def _assess_market_activity(self, volumes: Dict[str, Decimal]) -> bool:
        """
        Assess if market is active per ASC 820

        Active market characteristics:
        - Regular transactions
        - Sufficient volume
        - Price information readily available
        - Transactions between independent parties
        """
        total_volume = sum(volumes.values())
        num_exchanges = len([v for v in volumes.values() if v > 0])

        # Simple heuristic: active if multiple exchanges with volume
        return num_exchanges >= 2 and total_volume > Decimal("100000")

    def _calculate_adjusted_fair_value(
        self,
        asset_type: str,
        prices: Dict[str, Decimal],
        volumes: Dict[str, Decimal]
    ) -> Decimal:
        """
        Calculate adjusted fair value for less active markets

        May apply:
        - Liquidity discounts
        - Size adjustments
        - Other market-specific factors
        """
        # Use VWAP as base
        total_volume = sum(volumes.values())
        if total_volume > 0:
            vwap = sum(
                price * volumes[exchange] / total_volume
                for exchange, price in prices.items()
            )
        else:
            vwap = statistics.mean(prices.values())

        # Apply liquidity discount (5% example)
        liquidity_discount = Decimal("0.05")
        adjusted_value = vwap * (Decimal("1") - liquidity_discount)

        return adjusted_value

    async def reconcile_to_cost_basis(
        self,
        fair_value: Decimal,
        cost_basis: Decimal,
        asset_type: str
    ) -> Dict[str, Decimal]:
        """
        Reconcile fair value to cost basis

        Per ASC 820, disclose reconciliation for Level 3 measurements
        """
        return {
            "beginning_balance_cost": cost_basis,
            "purchases": Decimal("0"),
            "sales": Decimal("0"),
            "unrealized_gains": fair_value - cost_basis,
            "ending_balance_fair_value": fair_value
        }

    def generate_fair_value_disclosure(self) -> Dict:
        """
        Generate ASC 820 disclosure requirements

        Required disclosures:
        - Fair value hierarchy levels
        - Valuation techniques
        - Inputs (observable/unobservable)
        - Reconciliations for Level 3
        """
        level_1_total = sum(
            m.fair_value for m in self.measurements
            if m.hierarchy_level == FairValueLevel.LEVEL_1
        )
        level_2_total = sum(
            m.fair_value for m in self.measurements
            if m.hierarchy_level == FairValueLevel.LEVEL_2
        )
        level_3_total = sum(
            m.fair_value for m in self.measurements
            if m.hierarchy_level == FairValueLevel.LEVEL_3
        )

        return {
            "fair_value_hierarchy": {
                "level_1": str(level_1_total),
                "level_2": str(level_2_total),
                "level_3": str(level_3_total),
                "total": str(level_1_total + level_2_total + level_3_total)
            },
            "valuation_techniques": {
                asset_type: {
                    "technique": m.valuation_technique.value,
                    "principal_market": m.principal_market,
                    "hierarchy_level": m.hierarchy_level.value
                }
                for asset_type, m in {m.asset_type: m for m in self.measurements}.items()
            },
            "measurement_count": len(self.measurements)
        }


class RevenueRecognitionEngine:
    """
    Revenue Recognition Engine per ASC 606

    Five-step model for revenue recognition:
    1. Identify the contract with customer
    2. Identify performance obligations
    3. Determine transaction price
    4. Allocate price to performance obligations
    5. Recognize revenue when obligations satisfied
    """

    def __init__(self):
        self.revenue_events: List[RevenueRecognitionEvent] = []

    async def recognize_arbitrage_revenue(
        self,
        trade_id: str,
        buy_price: Decimal,
        sell_price: Decimal,
        quantity: Decimal,
        buy_fee: Decimal,
        sell_fee: Decimal,
        execution_date: datetime
    ) -> RevenueRecognitionEvent:
        """
        Recognize revenue from arbitrage trade per ASC 606

        Contract: Arbitrage trade execution
        Performance Obligation: Complete buy and sell transactions
        Transaction Price: Net proceeds after fees
        Recognition: Point in time when both trades settle
        """

        # Step 1: Identify contract
        contract_id = f"ARB-{trade_id}"

        # Step 2: Identify performance obligations
        performance_obligations = [
            "Execute buy transaction",
            "Execute sell transaction",
            "Settle both transactions"
        ]

        # Step 3: Determine transaction price
        gross_proceeds = sell_price * quantity
        cost_of_acquisition = buy_price * quantity
        total_fees = buy_fee + sell_fee

        transaction_price = gross_proceeds - cost_of_acquisition - total_fees

        # Step 4: Allocate transaction price (single obligation for arbitrage)
        allocated_prices = {
            "arbitrage_execution": transaction_price
        }

        # Step 5: Recognize revenue (point in time - when settled)
        revenue_recognized = transaction_price if transaction_price > 0 else Decimal("0")

        event = RevenueRecognitionEvent(
            event_id=f"REV-{trade_id}",
            recognition_date=execution_date,
            contract_id=contract_id,
            contract_type="arbitrage_trade",
            performance_obligations=performance_obligations,
            transaction_price=transaction_price,
            allocated_prices=allocated_prices,
            revenue_recognized=revenue_recognized,
            revenue_category=RevenueCategory.TRADING_REVENUE,
            supporting_docs=[f"trade_{trade_id}.json"]
        )

        self.revenue_events.append(event)

        logger.info(
            f"Revenue recognized for arbitrage trade {trade_id}: "
            f"${revenue_recognized:.2f}"
        )

        return event

    async def recognize_realized_gains(
        self,
        disposition_id: str,
        proceeds: Decimal,
        cost_basis: Decimal,
        disposition_date: datetime,
        asset_type: str
    ) -> RevenueRecognitionEvent:
        """
        Recognize realized gains from asset disposition

        Note: Realized gains are separate from trading revenue
        per GAAP classification
        """

        gain_or_loss = proceeds - cost_basis

        event = RevenueRecognitionEvent(
            event_id=f"GAIN-{disposition_id}",
            recognition_date=disposition_date,
            contract_id=disposition_id,
            contract_type="asset_disposition",
            performance_obligations=["Dispose of digital asset"],
            transaction_price=gain_or_loss,
            revenue_recognized=gain_or_loss if gain_or_loss > 0 else Decimal("0"),
            revenue_category=RevenueCategory.REALIZED_GAINS,
            supporting_docs=[f"disposition_{disposition_id}.json"]
        )

        self.revenue_events.append(event)

        logger.info(
            f"Realized {'gain' if gain_or_loss > 0 else 'loss'} recognized "
            f"for {asset_type}: ${abs(gain_or_loss):.2f}"
        )

        return event

    def calculate_total_revenue(
        self,
        start_date: datetime,
        end_date: datetime,
        category: Optional[RevenueCategory] = None
    ) -> Decimal:
        """
        Calculate total revenue for period

        Can filter by category (trading revenue, realized gains, etc.)
        """
        events = [
            e for e in self.revenue_events
            if start_date <= e.recognition_date <= end_date
        ]

        if category:
            events = [e for e in events if e.revenue_category == category]

        total = sum(e.revenue_recognized for e in events)

        return total

    def generate_revenue_disclosure(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """
        Generate ASC 606 revenue disclosure

        Required disclosures:
        - Disaggregation of revenue
        - Contract balances
        - Performance obligations
        - Significant judgments
        """
        events = [
            e for e in self.revenue_events
            if start_date <= e.recognition_date <= end_date
        ]

        # Disaggregate by category
        revenue_by_category = {}
        for category in RevenueCategory:
            category_revenue = sum(
                e.revenue_recognized for e in events
                if e.revenue_category == category
            )
            revenue_by_category[category.value] = str(category_revenue)

        return {
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_revenue": str(sum(e.revenue_recognized for e in events)),
            "revenue_by_category": revenue_by_category,
            "transaction_count": len(events),
            "performance_obligations": {
                "arbitrage_trades": "Complete buy and sell transactions simultaneously",
                "asset_dispositions": "Transfer control of digital asset to buyer"
            },
            "recognition_timing": "Point in time (trade settlement)",
            "significant_judgments": [
                "Transaction price excludes fees paid to exchanges",
                "Revenue recognized when both legs of arbitrage settle",
                "Fair value used for non-cash consideration"
            ]
        }


__all__ = [
    "FairValueLevel",
    "ValuationTechnique",
    "RevenueCategory",
    "FairValueMeasurement",
    "RevenueRecognitionEvent",
    "FairValueEngine",
    "RevenueRecognitionEngine"
]
