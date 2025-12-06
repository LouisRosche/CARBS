"""
Trading Strategy Module

Combines sentiment signals with price action for trading decisions.
Optimized for small capital with fee-awareness.

Strategies:
1. Sentiment-Momentum: Trade sentiment shifts with price confirmation
2. Fear-Greed Contrarian: Buy extreme fear, sell extreme greed
3. News Spike: React to unusual news velocity
4. Divergence: Sentiment/price divergence trades
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
import statistics

from . import (
    SignalService, SignalGenerator, SentimentAggregator,
    TradingSignal, SignalType, SentimentLevel
)

logger = logging.getLogger(__name__)


class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"
    NONE = "none"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


@dataclass
class PriceData:
    """Price data point"""
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source: str = "unknown"


@dataclass
class TradeSetup:
    """
    Complete trade setup with entry, exit, and risk parameters
    """
    setup_id: str
    timestamp: datetime
    asset: str
    side: PositionSide

    # Entry
    entry_price: Decimal
    entry_type: OrderType = OrderType.LIMIT

    # Risk management
    stop_loss: Decimal = None
    take_profit: Decimal = None
    risk_reward_ratio: float = 0.0

    # Position sizing
    position_size_usd: Decimal = Decimal("0")
    position_size_units: Decimal = Decimal("0")

    # Fee impact
    estimated_fees_usd: Decimal = Decimal("0")
    breakeven_move_percent: float = 0.0

    # Signal info
    signal: TradingSignal = None
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)

    # Tracking
    status: str = "pending"  # pending, active, closed, cancelled
    actual_entry: Decimal = None
    actual_exit: Decimal = None
    pnl_usd: Decimal = None


@dataclass
class ExchangeFees:
    """Exchange fee structure"""
    exchange: str
    maker_fee: Decimal  # Limit orders
    taker_fee: Decimal  # Market orders
    withdrawal_fee: Dict[str, Decimal] = field(default_factory=dict)  # Per asset


# Common exchange fees (as of 2024)
EXCHANGE_FEES = {
    "binance": ExchangeFees(
        exchange="binance",
        maker_fee=Decimal("0.001"),   # 0.1%
        taker_fee=Decimal("0.001"),   # 0.1%
    ),
    "binance_bnb": ExchangeFees(  # With BNB discount
        exchange="binance",
        maker_fee=Decimal("0.00075"),  # 0.075%
        taker_fee=Decimal("0.00075"),
    ),
    "coinbase": ExchangeFees(
        exchange="coinbase",
        maker_fee=Decimal("0.004"),   # 0.4%
        taker_fee=Decimal("0.006"),   # 0.6%
    ),
    "coinbase_advanced": ExchangeFees(  # Coinbase Advanced/Pro
        exchange="coinbase",
        maker_fee=Decimal("0.004"),   # 0.4%
        taker_fee=Decimal("0.006"),   # 0.6%
    ),
    "kraken": ExchangeFees(
        exchange="kraken",
        maker_fee=Decimal("0.0016"),  # 0.16%
        taker_fee=Decimal("0.0026"),  # 0.26%
    ),
    "kucoin": ExchangeFees(
        exchange="kucoin",
        maker_fee=Decimal("0.001"),   # 0.1%
        taker_fee=Decimal("0.001"),   # 0.1%
    ),
    "bybit": ExchangeFees(
        exchange="bybit",
        maker_fee=Decimal("0.001"),   # 0.1%
        taker_fee=Decimal("0.001"),   # 0.1%
    ),
    "mexc": ExchangeFees(
        exchange="mexc",
        maker_fee=Decimal("0"),       # 0% maker!
        taker_fee=Decimal("0.001"),   # 0.1%
    ),
    "gate": ExchangeFees(
        exchange="gate",
        maker_fee=Decimal("0.002"),   # 0.2%
        taker_fee=Decimal("0.002"),   # 0.2%
    ),
}


class FeeAwarePositionSizer:
    """
    Position sizing that accounts for fees

    For small capital ($100), fees can eat 1-2% per round trip.
    This module ensures trades are only taken when expected profit > fees.
    """

    def __init__(
        self,
        portfolio_value: Decimal,
        exchange_fees: ExchangeFees,
        max_position_pct: float = 0.25,  # Max 25% per trade
        min_profit_after_fees: float = 0.005  # Min 0.5% profit after fees
    ):
        self.portfolio_value = portfolio_value
        self.fees = exchange_fees
        self.max_position_pct = max_position_pct
        self.min_profit_after_fees = min_profit_after_fees

    def calculate_position(
        self,
        entry_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
        confidence: float,
        use_limit_orders: bool = True
    ) -> Dict:
        """
        Calculate optimal position size

        Returns position details including fee impact.
        """
        # Risk per trade based on confidence
        base_risk_pct = 0.02  # 2% base risk
        risk_pct = base_risk_pct * confidence  # Scale by confidence

        # Calculate stop distance
        if stop_loss and entry_price > 0:
            stop_distance_pct = abs(float(entry_price - stop_loss) / float(entry_price))
        else:
            stop_distance_pct = 0.05  # Default 5% stop

        # Position size based on risk
        risk_amount = self.portfolio_value * Decimal(str(risk_pct))
        position_size = risk_amount / Decimal(str(stop_distance_pct))

        # Apply max position limit
        max_position = self.portfolio_value * Decimal(str(self.max_position_pct))
        position_size = min(position_size, max_position)

        # Calculate fees
        fee_rate = self.fees.maker_fee if use_limit_orders else self.fees.taker_fee
        # Round trip fees (entry + exit)
        total_fees = position_size * fee_rate * 2
        fees_pct = float(fee_rate * 2)

        # Calculate breakeven move
        breakeven_move = fees_pct

        # Calculate expected profit
        if take_profit and entry_price > 0:
            profit_distance_pct = abs(float(take_profit - entry_price) / float(entry_price))
            expected_profit_pct = profit_distance_pct - fees_pct
        else:
            expected_profit_pct = 0

        # Risk/reward ratio
        if stop_distance_pct > 0 and profit_distance_pct:
            risk_reward = profit_distance_pct / stop_distance_pct
        else:
            risk_reward = 0

        # Check if trade is viable
        is_viable = (
            expected_profit_pct >= self.min_profit_after_fees and
            risk_reward >= 1.5 and
            position_size >= Decimal("10")  # Minimum $10 position
        )

        return {
            "position_size_usd": position_size,
            "position_units": position_size / entry_price if entry_price > 0 else Decimal("0"),
            "estimated_fees_usd": total_fees,
            "fees_percent": fees_pct * 100,
            "breakeven_move_percent": breakeven_move * 100,
            "expected_profit_percent": expected_profit_pct * 100,
            "risk_reward_ratio": risk_reward,
            "risk_amount_usd": risk_amount,
            "is_viable": is_viable,
            "rejection_reason": None if is_viable else self._get_rejection_reason(
                expected_profit_pct, risk_reward, position_size
            )
        }

    def _get_rejection_reason(
        self,
        expected_profit: float,
        risk_reward: float,
        position_size: Decimal
    ) -> str:
        """Get reason for trade rejection"""
        if expected_profit < self.min_profit_after_fees:
            return f"Expected profit {expected_profit*100:.2f}% < minimum {self.min_profit_after_fees*100:.2f}%"
        if risk_reward < 1.5:
            return f"Risk/reward {risk_reward:.2f} < minimum 1.5"
        if position_size < 10:
            return f"Position size ${position_size:.2f} < minimum $10"
        return "Unknown"

    def get_min_profitable_move(self) -> float:
        """
        Get minimum price move needed for profitable trade

        For small capital, this is crucial information.
        """
        # Round trip with market orders (worst case)
        worst_case_fees = float(self.fees.taker_fee * 2)

        # Add buffer for slippage
        slippage_buffer = 0.001  # 0.1%

        return (worst_case_fees + slippage_buffer) * 100  # Return as percentage


class TradingStrategy:
    """
    Main trading strategy combining signals with execution logic
    """

    def __init__(
        self,
        signal_service: SignalService,
        portfolio_value: Decimal = Decimal("100"),
        exchange: str = "binance",
        alert_callback: Callable = None
    ):
        self.signal_service = signal_service
        self.portfolio_value = portfolio_value
        self.exchange = exchange
        self.alert_callback = alert_callback

        # Get fee structure
        self.fees = EXCHANGE_FEES.get(exchange, EXCHANGE_FEES["binance"])

        # Position sizer
        self.position_sizer = FeeAwarePositionSizer(
            portfolio_value=portfolio_value,
            exchange_fees=self.fees
        )

        # Price data cache
        self._price_cache: Dict[str, List[PriceData]] = {}

        # Active setups
        self._active_setups: List[TradeSetup] = []

        # Strategy parameters
        self.params = {
            "min_confidence": 0.6,
            "default_stop_pct": 0.03,      # 3% stop loss
            "default_target_pct": 0.05,    # 5% take profit
            "max_open_positions": 2,
            "require_price_confirmation": True
        }

    async def evaluate_opportunities(
        self,
        assets: List[str] = None
    ) -> List[TradeSetup]:
        """
        Evaluate current opportunities and generate trade setups
        """
        if assets is None:
            assets = ["BTC", "ETH", "SOL"]

        setups = []

        # Get current signals
        signals = await self.signal_service.generator.generate_signals(
            assets=assets,
            include_market=True
        )

        for signal in signals:
            if signal.confidence < self.params["min_confidence"]:
                continue

            if signal.asset == "MARKET":
                # Market-wide signal - could apply to all assets
                continue

            setup = await self._create_setup(signal)
            if setup:
                setups.append(setup)

        return setups

    async def _create_setup(self, signal: TradingSignal) -> Optional[TradeSetup]:
        """Create trade setup from signal"""
        # Get current price (would come from exchange in production)
        current_price = await self._get_current_price(signal.asset)
        if not current_price:
            return None

        # Determine side
        if signal.signal_type in [SignalType.STRONG_BUY, SignalType.BUY]:
            side = PositionSide.LONG
            stop_loss = current_price * (1 - Decimal(str(self.params["default_stop_pct"])))
            take_profit = current_price * (1 + Decimal(str(self.params["default_target_pct"])))
        elif signal.signal_type in [SignalType.STRONG_SELL, SignalType.SELL]:
            side = PositionSide.SHORT
            stop_loss = current_price * (1 + Decimal(str(self.params["default_stop_pct"])))
            take_profit = current_price * (1 - Decimal(str(self.params["default_target_pct"])))
        else:
            return None

        # Calculate position size
        position = self.position_sizer.calculate_position(
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=signal.confidence,
            use_limit_orders=True
        )

        if not position["is_viable"]:
            logger.info(
                f"Setup rejected for {signal.asset}: {position['rejection_reason']}"
            )
            return None

        setup = TradeSetup(
            setup_id=signal.signal_id,
            timestamp=datetime.now(timezone.utc),
            asset=signal.asset,
            side=side,
            entry_price=current_price,
            entry_type=OrderType.LIMIT,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=position["risk_reward_ratio"],
            position_size_usd=position["position_size_usd"],
            position_size_units=position["position_units"],
            estimated_fees_usd=position["estimated_fees_usd"],
            breakeven_move_percent=position["breakeven_move_percent"],
            signal=signal,
            confidence=signal.confidence,
            reasons=signal.reasons
        )

        return setup

    async def _get_current_price(self, asset: str) -> Optional[Decimal]:
        """
        Get current price for asset

        In production, this would call exchange API.
        For now, returns mock data.
        """
        # Mock prices - in production, call exchange
        mock_prices = {
            "BTC": Decimal("67500"),
            "ETH": Decimal("3450"),
            "SOL": Decimal("175"),
            "XRP": Decimal("0.52"),
            "DOGE": Decimal("0.12")
        }
        return mock_prices.get(asset)

    def get_strategy_summary(self) -> Dict:
        """Get summary of strategy status"""
        min_move = self.position_sizer.get_min_profitable_move()

        return {
            "portfolio_value": float(self.portfolio_value),
            "exchange": self.exchange,
            "fees": {
                "maker": float(self.fees.maker_fee * 100),
                "taker": float(self.fees.taker_fee * 100)
            },
            "min_profitable_move_percent": min_move,
            "active_setups": len(self._active_setups),
            "parameters": self.params
        }


class SmallCapitalOptimizer:
    """
    Optimizations specifically for small capital (<$1000)

    Key insights:
    1. Use limit orders only (0% maker fees on some exchanges)
    2. Trade less frequently, higher conviction only
    3. Focus on volatile assets with larger moves
    4. Consider futures for capital efficiency (with caution)
    """

    # Exchanges with 0% or very low maker fees
    ZERO_FEE_EXCHANGES = ["mexc"]
    LOW_FEE_EXCHANGES = ["binance", "kucoin", "bybit"]

    @staticmethod
    def get_recommended_exchange(capital: Decimal) -> Dict:
        """
        Get exchange recommendation based on capital
        """
        capital_float = float(capital)

        if capital_float < 100:
            return {
                "primary": "mexc",
                "reason": "0% maker fees critical for tiny capital",
                "alternative": "binance",
                "warnings": [
                    "With <$100, even small fees significantly impact returns",
                    "Consider paper trading until capital grows",
                    "Focus on high-conviction trades only"
                ],
                "strategy": "limit_orders_only"
            }
        elif capital_float < 500:
            return {
                "primary": "binance",
                "reason": "Low fees + high liquidity",
                "alternative": "kucoin",
                "warnings": [
                    "Use BNB for fee discounts on Binance",
                    "Stick to major pairs (BTC, ETH) for liquidity"
                ],
                "strategy": "limit_orders_preferred"
            }
        elif capital_float < 5000:
            return {
                "primary": "binance",
                "reason": "Best overall for growing accounts",
                "alternative": "kraken",
                "warnings": [
                    "Can start using market orders for urgent signals"
                ],
                "strategy": "mixed_orders"
            }
        else:
            return {
                "primary": "binance",
                "reason": "Liquidity and features",
                "alternative": "coinbase",
                "warnings": [],
                "strategy": "optimal_execution"
            }

    @staticmethod
    def calculate_minimum_trade_size(
        exchange: str,
        expected_move_pct: float
    ) -> Decimal:
        """
        Calculate minimum viable trade size

        Trade must be large enough that expected profit > fees
        """
        fees = EXCHANGE_FEES.get(exchange, EXCHANGE_FEES["binance"])

        # Round trip fees
        round_trip_fee_pct = float(fees.maker_fee * 2)

        if expected_move_pct <= round_trip_fee_pct:
            return Decimal("0")  # Trade not viable at any size

        # Minimum to make at least $1 profit
        min_profit = Decimal("1")
        net_move_pct = Decimal(str(expected_move_pct - round_trip_fee_pct))

        if net_move_pct > 0:
            min_trade_size = min_profit / net_move_pct
            return max(min_trade_size, Decimal("10"))  # At least $10

        return Decimal("0")

    @staticmethod
    def get_small_capital_rules() -> Dict:
        """
        Trading rules for small capital
        """
        return {
            "position_sizing": {
                "max_per_trade_pct": 25,  # Max 25% per trade
                "max_open_positions": 2,
                "scale_in": False,  # Don't scale in with small capital
            },
            "order_execution": {
                "use_limit_orders": True,
                "avoid_market_orders": True,
                "patience_required": True,
            },
            "trade_selection": {
                "min_confidence": 0.7,  # Higher bar
                "min_expected_move_pct": 2.0,  # Need bigger moves
                "prefer_volatile_assets": True,
            },
            "risk_management": {
                "max_daily_loss_pct": 5,
                "stop_loss_required": True,
                "take_profit_required": True,
            },
            "mindset": [
                "Small capital = learning phase",
                "Focus on process, not profits",
                "Every trade is tuition",
                "Size up only after consistent profits",
                "Paper trade strategies first"
            ]
        }


# Quick test / usage example
async def demo():
    """Demo the signal and strategy system"""
    from pathlib import Path

    # Create signal service
    signal_service = SignalService(
        data_dir=Path("data/signals"),
        update_interval=60
    )

    # Create strategy
    strategy = TradingStrategy(
        signal_service=signal_service,
        portfolio_value=Decimal("100"),
        exchange="binance"
    )

    # Get recommendations
    rec = SmallCapitalOptimizer.get_recommended_exchange(Decimal("100"))
    print(f"\nExchange recommendation: {rec['primary']}")
    print(f"Reason: {rec['reason']}")
    print(f"Warnings: {rec['warnings']}")

    # Get strategy summary
    summary = strategy.get_strategy_summary()
    print(f"\nStrategy Summary:")
    print(f"  Min profitable move: {summary['min_profitable_move_percent']:.2f}%")

    # Get trading rules
    rules = SmallCapitalOptimizer.get_small_capital_rules()
    print(f"\nTrading Rules for Small Capital:")
    for mindset in rules["mindset"]:
        print(f"  • {mindset}")


if __name__ == "__main__":
    asyncio.run(demo())
