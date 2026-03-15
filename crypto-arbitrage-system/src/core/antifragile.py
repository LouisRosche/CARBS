"""
Anti-Fragile Trading Core

The central nervous system that:
- Learns from every trade and market event
- Adapts strategies based on regime changes
- Incorporates new research and findings
- Stress-tests strategies continuously
- Fails gracefully under extreme conditions
- Gets stronger from volatility and stress

Philosophy: The system should IMPROVE from disorder, not just survive it.
"""

import asyncio
import logging
import hashlib
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from collections import deque
from enum import Enum
import json
import random

logger = logging.getLogger(__name__)


class SystemState(Enum):
    """Overall system state"""
    LEARNING = "learning"       # Gathering data, not trading
    CAUTIOUS = "cautious"       # Trading conservatively
    NORMAL = "normal"           # Standard operation
    AGGRESSIVE = "aggressive"   # High confidence, increased size
    DEFENSIVE = "defensive"     # Market stress, reduced exposure
    HALTED = "halted"           # Emergency stop


@dataclass
class StrategyPerformance:
    """Track strategy performance metrics"""
    strategy_name: str
    total_trades: int = 0
    winning_trades: int = 0
    total_pnl: Decimal = Decimal("0")
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    avg_win: Decimal = Decimal("0")
    avg_loss: Decimal = Decimal("0")
    profit_factor: float = 0.0
    last_updated: datetime = None

    # Anti-fragility metrics
    volatility_adjusted_return: float = 0.0
    recovery_speed: float = 0.0  # How fast it recovers from drawdowns
    stress_performance: float = 0.0  # Performance during high vol


@dataclass
class MarketConditions:
    """Current market conditions snapshot"""
    timestamp: datetime
    regime: str
    volatility: float
    trend_strength: float
    sentiment_score: float
    fear_greed_index: int
    correlation_btc: float  # How correlated is the market to BTC
    volume_trend: str  # increasing, decreasing, stable


@dataclass
class AdaptiveParameters:
    """Strategy parameters that adapt to conditions"""
    base_position_size: float = 0.1
    position_size_multiplier: float = 1.0
    stop_loss_percent: float = 0.02
    take_profit_percent: float = 0.04
    min_confidence: float = 0.6
    max_daily_trades: int = 10
    max_drawdown_halt: float = 0.05  # Halt if 5% drawdown

    # Regime-specific adjustments
    regime_adjustments: Dict = field(default_factory=dict)


class AntifragileCore:
    """
    The anti-fragile trading system core

    Key principles:
    1. LEARN: Every trade, win or lose, provides information
    2. ADAPT: Parameters adjust based on what works
    3. STRESS TEST: Continuously validate strategies
    4. FAIL SAFE: Multiple circuit breakers
    5. DIVERSIFY: Don't bet everything on one strategy
    6. BENEFIT FROM DISORDER: High volatility = opportunity
    """

    def __init__(
        self,
        data_dir: Path = None,
        initial_capital: Decimal = Decimal("100"),
        alert_callback: Callable = None,
        kelly_max_fraction: float = 0.25
    ):
        self.data_dir = data_dir or Path("data/antifragile")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.alert_callback = alert_callback
        self.kelly_max_fraction = kelly_max_fraction

        logger.info(f"AntifragileCore kelly_max_fraction={self.kelly_max_fraction}")

        # System state
        self.state = SystemState.LEARNING
        self.state_history: deque = deque(maxlen=1000)

        # Strategy tracking
        self.strategies: Dict[str, StrategyPerformance] = {}
        self.active_strategy: str = None

        # Parameters
        self.params = AdaptiveParameters()

        # Market conditions
        self.conditions: MarketConditions = None
        self.conditions_history: deque = deque(maxlen=168)  # 1 week hourly

        # Learning data
        self.trade_history: deque = deque(maxlen=10000)
        self.daily_pnl: deque = deque(maxlen=365)
        self.lessons_learned: List[Dict] = []

        # Circuit breakers
        self.daily_loss = Decimal("0")
        self.daily_trades = 0
        self.consecutive_losses = 0
        self.last_trade_time: datetime = None

        # Load state
        self._load_state()

    def _load_state(self):
        """Load persistent state"""
        state_file = self.data_dir / "core_state.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    data = json.load(f)
                    self.current_capital = Decimal(data.get("current_capital", str(self.initial_capital)))
                    self.lessons_learned = data.get("lessons_learned", [])

                    # Load strategy performance
                    for name, perf in data.get("strategies", {}).items():
                        self.strategies[name] = StrategyPerformance(
                            strategy_name=name,
                            total_trades=perf.get("total_trades", 0),
                            winning_trades=perf.get("winning_trades", 0),
                            total_pnl=Decimal(perf.get("total_pnl", "0")),
                            win_rate=perf.get("win_rate", 0),
                            sharpe_ratio=perf.get("sharpe_ratio", 0)
                        )

            except Exception as e:
                logger.error(f"Failed to load core state: {e}")

    def _save_state(self):
        """Save persistent state"""
        state_file = self.data_dir / "core_state.json"

        data = {
            "current_capital": str(self.current_capital),
            "lessons_learned": self.lessons_learned[-100:],  # Keep last 100
            "strategies": {
                name: {
                    "total_trades": perf.total_trades,
                    "winning_trades": perf.winning_trades,
                    "total_pnl": str(perf.total_pnl),
                    "win_rate": perf.win_rate,
                    "sharpe_ratio": perf.sharpe_ratio
                }
                for name, perf in self.strategies.items()
            },
            "last_updated": datetime.now(timezone.utc).isoformat()
        }

        with open(state_file, 'w') as f:
            json.dump(data, f, indent=2)

    async def update_conditions(
        self,
        regime: str,
        volatility: float,
        sentiment: float,
        fear_greed: int
    ):
        """Update market conditions and adapt"""
        self.conditions = MarketConditions(
            timestamp=datetime.now(timezone.utc),
            regime=regime,
            volatility=volatility,
            trend_strength=0.0,  # Would calculate from price data
            sentiment_score=sentiment,
            fear_greed_index=fear_greed,
            correlation_btc=1.0,
            volume_trend="stable"
        )

        self.conditions_history.append(self.conditions)

        # Adapt parameters based on conditions
        await self._adapt_to_conditions()

    async def _adapt_to_conditions(self):
        """Adapt parameters based on current conditions"""
        if not self.conditions:
            return

        # Volatility adaptation
        if self.conditions.volatility > 0.05:  # High volatility
            self.params.position_size_multiplier = 0.5
            self.params.stop_loss_percent = 0.04  # Wider stops
            self.params.take_profit_percent = 0.06  # Larger targets

            if self.state != SystemState.HALTED:
                self.state = SystemState.DEFENSIVE

            logger.info("Adapted to HIGH VOLATILITY: Reduced position sizes, wider stops")

        elif self.conditions.volatility < 0.01:  # Low volatility
            self.params.position_size_multiplier = 1.2
            self.params.stop_loss_percent = 0.015
            self.params.take_profit_percent = 0.025

            logger.info("Adapted to LOW VOLATILITY: Normal positions, tighter stops")

        # Fear/Greed adaptation
        if self.conditions.fear_greed_index < 20:  # Extreme fear
            # Contrarian: This is often a buying opportunity
            self.params.min_confidence = 0.5  # Lower bar for buys
            self.state = SystemState.CAUTIOUS

            self._record_lesson(
                "extreme_fear",
                "Market in extreme fear - historically good buying opportunity",
                {"fear_greed": self.conditions.fear_greed_index}
            )

        elif self.conditions.fear_greed_index > 80:  # Extreme greed
            # Contrarian: Time to be cautious
            self.params.min_confidence = 0.8  # Higher bar
            self.params.position_size_multiplier *= 0.7

            self._record_lesson(
                "extreme_greed",
                "Market in extreme greed - increased caution",
                {"fear_greed": self.conditions.fear_greed_index}
            )

        # Regime adaptation
        regime_settings = {
            "bull": {
                "position_multiplier": 1.2,
                "bias": "long",
                "state": SystemState.NORMAL
            },
            "bear": {
                "position_multiplier": 0.7,
                "bias": "short",
                "state": SystemState.CAUTIOUS
            },
            "sideways": {
                "position_multiplier": 0.8,
                "bias": "neutral",
                "state": SystemState.CAUTIOUS
            }
        }

        if self.conditions.regime in regime_settings:
            settings = regime_settings[self.conditions.regime]
            self.params.position_size_multiplier *= settings["position_multiplier"]

            if self.state not in [SystemState.HALTED, SystemState.DEFENSIVE]:
                self.state = settings["state"]

    def _record_lesson(self, lesson_type: str, description: str, context: Dict):
        """Record a lesson learned for future reference"""
        lesson = {
            "id": hashlib.sha256(
                f"{lesson_type}:{datetime.now().isoformat()}".encode()
            ).hexdigest()[:12],
            "type": lesson_type,
            "description": description,
            "context": context,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        self.lessons_learned.append(lesson)

        logger.info(f"Lesson learned: {description}")

    async def evaluate_trade(
        self,
        strategy_name: str,
        signal_confidence: float,
        expected_return: float,
        current_price: Decimal
    ) -> Dict:
        """
        Evaluate if a trade should be taken

        Returns decision with reasoning
        """
        decision = {
            "take_trade": False,
            "reasons": [],
            "adjusted_size": 0.0,
            "stop_loss": None,
            "take_profit": None
        }

        # Check circuit breakers first
        breaker_result = self._check_circuit_breakers()
        if breaker_result["triggered"]:
            decision["reasons"].append(f"Circuit breaker: {breaker_result['reason']}")
            return decision

        # Check minimum confidence
        adjusted_min_confidence = self.params.min_confidence
        if self.state == SystemState.CAUTIOUS:
            adjusted_min_confidence += 0.1
        elif self.state == SystemState.AGGRESSIVE:
            adjusted_min_confidence -= 0.1

        if signal_confidence < adjusted_min_confidence:
            decision["reasons"].append(
                f"Confidence {signal_confidence:.0%} below threshold {adjusted_min_confidence:.0%}"
            )
            return decision

        # Check expected return vs fees
        min_return = 0.002  # 0.2% minimum
        if self.state == SystemState.CAUTIOUS:
            min_return = 0.004

        if expected_return < min_return:
            decision["reasons"].append(
                f"Expected return {expected_return:.2%} below minimum {min_return:.2%}"
            )
            return decision

        # Check strategy performance
        if strategy_name in self.strategies:
            perf = self.strategies[strategy_name]
            if perf.total_trades >= 10 and perf.win_rate < 0.4:
                decision["reasons"].append(
                    f"Strategy {strategy_name} win rate too low ({perf.win_rate:.0%})"
                )
                return decision

        # Calculate position size
        base_size = float(self.current_capital) * self.params.base_position_size
        adjusted_size = base_size * self.params.position_size_multiplier

        # Confidence scaling
        adjusted_size *= (0.5 + signal_confidence * 0.5)

        # Apply Kelly-like sizing based on win rate
        if strategy_name in self.strategies and self.strategies[strategy_name].total_trades >= 20:
            perf = self.strategies[strategy_name]
            if perf.win_rate > 0 and perf.avg_loss > 0:
                # Simplified Kelly: f = W - (1-W)/R where W=win rate, R=win/loss ratio
                win_loss_ratio = float(perf.avg_win / perf.avg_loss) if perf.avg_loss > 0 else 1
                kelly = perf.win_rate - (1 - perf.win_rate) / win_loss_ratio
                kelly = max(0, min(self.kelly_max_fraction, kelly))  # Cap at configured max
                adjusted_size = float(self.current_capital) * kelly
                decision["reasons"].append(f"Kelly sizing: {kelly:.1%}")

        # Cap at max position size (configurable Kelly max fraction)
        max_size = float(self.current_capital) * self.kelly_max_fraction
        adjusted_size = min(adjusted_size, max_size)

        # Calculate stops
        stop_loss = current_price * Decimal(str(1 - self.params.stop_loss_percent))
        take_profit = current_price * Decimal(str(1 + self.params.take_profit_percent))

        decision["take_trade"] = True
        decision["adjusted_size"] = adjusted_size
        decision["stop_loss"] = stop_loss
        decision["take_profit"] = take_profit
        decision["reasons"].append(f"Trade approved: size=${adjusted_size:.2f}")

        return decision

    def _check_circuit_breakers(self) -> Dict:
        """Check all circuit breakers"""
        # Daily loss limit
        if self.daily_loss < -float(self.current_capital) * self.params.max_drawdown_halt:
            return {
                "triggered": True,
                "reason": f"Daily loss limit hit: ${self.daily_loss:.2f}"
            }

        # Daily trade limit
        if self.daily_trades >= self.params.max_daily_trades:
            return {
                "triggered": True,
                "reason": f"Daily trade limit reached: {self.daily_trades}"
            }

        # Consecutive losses
        if self.consecutive_losses >= 5:
            return {
                "triggered": True,
                "reason": f"Consecutive losses: {self.consecutive_losses}"
            }

        # Cooldown after trade
        if self.last_trade_time:
            cooldown = timedelta(minutes=5)
            if datetime.now(timezone.utc) - self.last_trade_time < cooldown:
                return {
                    "triggered": True,
                    "reason": "Trade cooldown active"
                }

        # System state
        if self.state == SystemState.HALTED:
            return {
                "triggered": True,
                "reason": "System halted"
            }

        return {"triggered": False}

    async def record_trade_result(
        self,
        strategy_name: str,
        pnl: Decimal,
        trade_details: Dict
    ):
        """Record trade result and learn from it"""
        is_win = pnl > 0

        # Update daily tracking
        self.daily_loss += pnl
        self.daily_trades += 1
        self.current_capital += pnl
        self.last_trade_time = datetime.now(timezone.utc)

        # Update consecutive losses
        if is_win:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1

        # Update strategy performance
        if strategy_name not in self.strategies:
            self.strategies[strategy_name] = StrategyPerformance(strategy_name=strategy_name)

        perf = self.strategies[strategy_name]
        perf.total_trades += 1
        perf.total_pnl += pnl
        if is_win:
            perf.winning_trades += 1
        perf.win_rate = perf.winning_trades / perf.total_trades
        perf.last_updated = datetime.now(timezone.utc)

        # Record trade
        self.trade_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "strategy": strategy_name,
            "pnl": str(pnl),
            "is_win": is_win,
            "details": trade_details,
            "conditions": {
                "regime": self.conditions.regime if self.conditions else None,
                "volatility": self.conditions.volatility if self.conditions else None,
                "fear_greed": self.conditions.fear_greed_index if self.conditions else None
            }
        })

        # Learn from result
        await self._learn_from_trade(strategy_name, pnl, trade_details, is_win)

        # Save state
        self._save_state()

        # Alert on significant events
        if self.alert_callback:
            if self.consecutive_losses >= 3:
                await self.alert_callback(
                    "Warning: Consecutive Losses",
                    f"{self.consecutive_losses} losses in a row. Consider pausing."
                )
            if float(self.daily_loss) < -float(self.current_capital) * 0.03:
                await self.alert_callback(
                    "Warning: Daily Loss Threshold",
                    f"Daily loss: ${self.daily_loss:.2f}"
                )

    async def _learn_from_trade(
        self,
        strategy_name: str,
        pnl: Decimal,
        details: Dict,
        is_win: bool
    ):
        """Extract lessons from trade"""
        conditions = self.conditions

        # Pattern detection
        if not is_win and conditions:
            # What went wrong?
            if conditions.volatility > 0.04:
                self._record_lesson(
                    "loss_high_vol",
                    f"Loss during high volatility ({conditions.volatility:.1%})",
                    {"strategy": strategy_name, "volatility": conditions.volatility}
                )

            if conditions.fear_greed_index > 70:
                self._record_lesson(
                    "loss_greed",
                    f"Loss during greed phase (FG: {conditions.fear_greed_index})",
                    {"strategy": strategy_name, "fear_greed": conditions.fear_greed_index}
                )

        elif is_win and conditions:
            # What went right?
            if conditions.fear_greed_index < 30:
                self._record_lesson(
                    "win_fear",
                    f"Win during fear phase - contrarian worked",
                    {"strategy": strategy_name, "fear_greed": conditions.fear_greed_index}
                )

        # Strategy-specific learning
        if strategy_name in self.strategies:
            perf = self.strategies[strategy_name]

            # Check if strategy is degrading
            if perf.total_trades >= 20:
                recent_trades = [
                    t for t in list(self.trade_history)[-20:]
                    if t.get("strategy") == strategy_name
                ]

                if recent_trades:
                    recent_wins = sum(1 for t in recent_trades if t.get("is_win"))
                    recent_win_rate = recent_wins / len(recent_trades)

                    if recent_win_rate < perf.win_rate * 0.7:
                        self._record_lesson(
                            "strategy_degradation",
                            f"Strategy {strategy_name} degrading: recent WR {recent_win_rate:.0%} vs overall {perf.win_rate:.0%}",
                            {"strategy": strategy_name, "recent_wr": recent_win_rate}
                        )

    async def stress_test(self) -> Dict:
        """
        Run stress tests on current strategies

        Simulates extreme conditions to find weaknesses.
        """
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tests": [],
            "recommendations": []
        }

        # Test 1: What if volatility doubles?
        original_vol_mult = self.params.position_size_multiplier
        await self.update_conditions(
            regime="high_vol",
            volatility=0.10,  # Extreme volatility
            sentiment=0.5,
            fear_greed=25
        )
        results["tests"].append({
            "name": "Extreme Volatility",
            "position_reduction": 1 - self.params.position_size_multiplier,
            "system_state": self.state.value
        })

        # Test 2: What if we hit max drawdown?
        self.daily_loss = -self.current_capital * Decimal("0.06")
        breaker = self._check_circuit_breakers()
        results["tests"].append({
            "name": "Max Drawdown",
            "circuit_breaker_triggered": breaker["triggered"],
            "reason": breaker.get("reason")
        })
        self.daily_loss = Decimal("0")  # Reset

        # Test 3: Consecutive losses
        original_losses = self.consecutive_losses
        self.consecutive_losses = 5
        breaker = self._check_circuit_breakers()
        results["tests"].append({
            "name": "Consecutive Losses",
            "circuit_breaker_triggered": breaker["triggered"],
            "reason": breaker.get("reason")
        })
        self.consecutive_losses = original_losses

        # Generate recommendations
        if len(self.strategies) == 1:
            results["recommendations"].append(
                "Consider adding more strategies for diversification"
            )

        low_performers = [
            name for name, perf in self.strategies.items()
            if perf.total_trades >= 10 and perf.win_rate < 0.45
        ]
        if low_performers:
            results["recommendations"].append(
                f"Review underperforming strategies: {', '.join(low_performers)}"
            )

        return results

    def get_system_health(self) -> Dict:
        """Get overall system health status"""
        health = {
            "state": self.state.value,
            "capital": {
                "initial": str(self.initial_capital),
                "current": str(self.current_capital),
                "return_pct": float((self.current_capital - self.initial_capital) / self.initial_capital * 100)
            },
            "daily": {
                "pnl": str(self.daily_loss),
                "trades": self.daily_trades
            },
            "strategies": {
                name: {
                    "trades": perf.total_trades,
                    "win_rate": f"{perf.win_rate:.1%}",
                    "pnl": str(perf.total_pnl)
                }
                for name, perf in self.strategies.items()
            },
            "circuit_breakers": {
                "consecutive_losses": self.consecutive_losses,
                "daily_trade_count": f"{self.daily_trades}/{self.params.max_daily_trades}"
            },
            "lessons_learned": len(self.lessons_learned),
            "conditions": {
                "regime": self.conditions.regime if self.conditions else "unknown",
                "volatility": f"{self.conditions.volatility:.1%}" if self.conditions else "unknown",
                "fear_greed": self.conditions.fear_greed_index if self.conditions else "unknown"
            } if self.conditions else None
        }

        return health

    async def daily_reset(self):
        """Reset daily counters"""
        # Record daily P&L
        self.daily_pnl.append({
            "date": datetime.now(timezone.utc).date().isoformat(),
            "pnl": str(self.daily_loss),
            "trades": self.daily_trades
        })

        # Reset
        self.daily_loss = Decimal("0")
        self.daily_trades = 0

        # Exit halted state if conditions improved
        if self.state == SystemState.HALTED:
            self.state = SystemState.CAUTIOUS
            logger.info("System moved from HALTED to CAUTIOUS after daily reset")

        self._save_state()

    def get_optimal_strategy(self) -> Optional[str]:
        """Get the best performing strategy for current conditions"""
        if not self.strategies:
            return None

        # Filter strategies with enough trades
        viable = {
            name: perf for name, perf in self.strategies.items()
            if perf.total_trades >= 10
        }

        if not viable:
            return list(self.strategies.keys())[0] if self.strategies else None

        # Score strategies
        scores = {}
        for name, perf in viable.items():
            # Base score on win rate and profit factor
            score = perf.win_rate * 0.4

            if perf.profit_factor > 0:
                score += min(perf.profit_factor * 0.1, 0.3)

            if perf.sharpe_ratio > 0:
                score += min(perf.sharpe_ratio * 0.1, 0.3)

            scores[name] = score

        # Return highest scoring
        return max(scores.keys(), key=lambda k: scores[k])


def create_antifragile_system(
    data_dir: Path = None,
    initial_capital: Decimal = Decimal("100"),
    alert_callback: Callable = None,
    kelly_max_fraction: float = 0.25
) -> AntifragileCore:
    """Factory function for creating anti-fragile system"""
    return AntifragileCore(
        data_dir=data_dir,
        initial_capital=initial_capital,
        alert_callback=alert_callback,
        kelly_max_fraction=kelly_max_fraction
    )


__all__ = [
    "SystemState",
    "StrategyPerformance",
    "MarketConditions",
    "AdaptiveParameters",
    "AntifragileCore",
    "create_antifragile_system"
]
