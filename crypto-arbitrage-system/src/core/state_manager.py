"""
Centralized State Manager

Provides unified state management for cross-component communication.
All components (engine, dashboard, API, CLI) can read/write to shared state.

Features:
- Thread-safe state access
- Event-based notifications
- Persistence support
- State snapshots for recovery
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from decimal import Decimal
from pathlib import Path
from collections import deque
import threading

logger = logging.getLogger(__name__)


def decimal_serializer(obj):
    """JSON serializer for Decimal and datetime"""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


@dataclass
class TradingState:
    """Current trading system state"""
    running: bool = False
    mode: str = "paper"  # paper or live
    emergency_stop: bool = False
    emergency_reason: str = ""
    started_at: Optional[datetime] = None

    # Performance metrics
    opportunities_detected: int = 0
    opportunities_scored: int = 0
    opportunities_executed: int = 0

    # Financial metrics
    initial_capital: Decimal = Decimal("10000")
    current_capital: Decimal = Decimal("10000")
    total_profit: Decimal = Decimal("0")
    total_fees: Decimal = Decimal("0")

    # Risk metrics
    daily_pnl: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    var_95: Decimal = Decimal("0")

    # Execution stats
    total_trades: int = 0
    successful_trades: int = 0
    failed_trades: int = 0
    avg_execution_time_ms: float = 0.0

    # Exchange connectivity
    exchanges_connected: List[str] = field(default_factory=list)
    exchange_status: Dict[str, str] = field(default_factory=dict)

    # Active positions
    open_positions: Dict[str, Dict] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        # Convert Decimal to string
        for key, value in data.items():
            if isinstance(value, Decimal):
                data[key] = str(value)
        return data


@dataclass
class SignalState:
    """Current signal and sentiment state"""
    market_sentiment: float = 50.0  # 0-100 (fear to greed)
    market_trend: str = "neutral"  # bearish, neutral, bullish

    # Per-asset sentiment
    asset_sentiment: Dict[str, float] = field(default_factory=dict)

    # Active signals
    active_signals: List[Dict] = field(default_factory=list)

    # News impact
    recent_news_count: int = 0
    news_sentiment: float = 50.0

    # Regime detection
    current_regime: str = "normal"  # normal, volatile, trending
    regime_confidence: float = 0.0


@dataclass
class SystemHealth:
    """System health and connectivity status"""
    healthy: bool = True
    last_heartbeat: Optional[datetime] = None

    # Component status
    database_connected: bool = False
    redis_connected: bool = False
    prometheus_running: bool = False

    # Exchange health
    exchange_latencies: Dict[str, float] = field(default_factory=dict)

    # Resource usage
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0

    # Error tracking
    recent_errors: List[str] = field(default_factory=list)
    error_count_1h: int = 0


class StateManager:
    """
    Centralized state manager with event notification

    Usage:
        state_mgr = StateManager.get_instance()

        # Update state
        state_mgr.update_trading_state(opportunities_detected=10)

        # Read state
        state = state_mgr.get_trading_state()

        # Subscribe to changes
        state_mgr.subscribe('trading', callback_fn)
    """

    _instance: Optional['StateManager'] = None
    _lock = threading.Lock()

    def __init__(self, persist_path: Path = None):
        """Initialize state manager (use get_instance() instead)"""
        self.persist_path = persist_path or Path("data/state")
        self.persist_path.mkdir(parents=True, exist_ok=True)

        # State objects
        self._trading_state = TradingState()
        self._signal_state = SignalState()
        self._system_health = SystemHealth()

        # Event subscribers
        self._subscribers: Dict[str, List[Callable]] = {
            'trading': [],
            'signal': [],
            'health': [],
            'all': []
        }

        # Recent trades for dashboard
        self._recent_trades: deque = deque(maxlen=100)

        # Recent opportunities
        self._recent_opportunities: deque = deque(maxlen=50)

        # State lock for thread safety
        self._state_lock = threading.RLock()

        # Load persisted state
        self._load_state()

    @classmethod
    def get_instance(cls, persist_path: Path = None) -> 'StateManager':
        """Get singleton instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(persist_path)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton (for testing)"""
        with cls._lock:
            cls._instance = None

    # Trading State Methods

    def get_trading_state(self) -> TradingState:
        """Get current trading state"""
        with self._state_lock:
            return self._trading_state

    def update_trading_state(self, **kwargs) -> None:
        """Update trading state fields"""
        with self._state_lock:
            for key, value in kwargs.items():
                if hasattr(self._trading_state, key):
                    setattr(self._trading_state, key, value)

            self._notify_subscribers('trading', self._trading_state)
            self._persist_state()

    def increment_counter(self, field: str, amount: int = 1) -> None:
        """Safely increment a counter field"""
        with self._state_lock:
            if hasattr(self._trading_state, field):
                current = getattr(self._trading_state, field)
                setattr(self._trading_state, field, current + amount)
                self._notify_subscribers('trading', self._trading_state)

    # Signal State Methods

    def get_signal_state(self) -> SignalState:
        """Get current signal state"""
        with self._state_lock:
            return self._signal_state

    def update_signal_state(self, **kwargs) -> None:
        """Update signal state fields"""
        with self._state_lock:
            for key, value in kwargs.items():
                if hasattr(self._signal_state, key):
                    setattr(self._signal_state, key, value)

            self._notify_subscribers('signal', self._signal_state)

    def add_active_signal(self, signal: Dict) -> None:
        """Add an active trading signal"""
        with self._state_lock:
            signal['timestamp'] = datetime.now(timezone.utc).isoformat()
            self._signal_state.active_signals.append(signal)

            # Keep only recent signals
            if len(self._signal_state.active_signals) > 20:
                self._signal_state.active_signals = self._signal_state.active_signals[-20:]

            self._notify_subscribers('signal', self._signal_state)

    def clear_expired_signals(self, max_age_seconds: int = 300) -> None:
        """Remove signals older than max_age"""
        with self._state_lock:
            now = datetime.now(timezone.utc)
            self._signal_state.active_signals = [
                s for s in self._signal_state.active_signals
                if (now - datetime.fromisoformat(s['timestamp'])).total_seconds() < max_age_seconds
            ]

    # System Health Methods

    def get_system_health(self) -> SystemHealth:
        """Get system health status"""
        with self._state_lock:
            return self._system_health

    def update_system_health(self, **kwargs) -> None:
        """Update system health fields"""
        with self._state_lock:
            for key, value in kwargs.items():
                if hasattr(self._system_health, key):
                    setattr(self._system_health, key, value)

            self._system_health.last_heartbeat = datetime.now(timezone.utc)
            self._notify_subscribers('health', self._system_health)

    def record_error(self, error: str) -> None:
        """Record an error"""
        with self._state_lock:
            self._system_health.recent_errors.append(
                f"{datetime.now(timezone.utc).isoformat()}: {error}"
            )
            self._system_health.error_count_1h += 1

            # Keep only last 50 errors
            if len(self._system_health.recent_errors) > 50:
                self._system_health.recent_errors = self._system_health.recent_errors[-50:]

    # Trade Recording

    def record_trade(self, trade: Dict) -> None:
        """Record a completed trade"""
        with self._state_lock:
            trade['recorded_at'] = datetime.now(timezone.utc).isoformat()
            self._recent_trades.append(trade)

            # Update counters
            self._trading_state.total_trades += 1
            if trade.get('success', False):
                self._trading_state.successful_trades += 1
            else:
                self._trading_state.failed_trades += 1

            # Update profit
            if 'net_profit' in trade:
                self._trading_state.total_profit += Decimal(str(trade['net_profit']))

            self._notify_subscribers('trading', self._trading_state)
            self._persist_state()

    def get_recent_trades(self, limit: int = 20) -> List[Dict]:
        """Get recent trades"""
        with self._state_lock:
            return list(self._recent_trades)[-limit:]

    # Opportunity Recording

    def record_opportunity(self, opportunity: Dict) -> None:
        """Record a detected opportunity"""
        with self._state_lock:
            opportunity['detected_at'] = datetime.now(timezone.utc).isoformat()
            self._recent_opportunities.append(opportunity)
            self._trading_state.opportunities_detected += 1

    def get_recent_opportunities(self, limit: int = 20) -> List[Dict]:
        """Get recent opportunities"""
        with self._state_lock:
            return list(self._recent_opportunities)[-limit:]

    # Event Subscription

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """
        Subscribe to state changes

        Args:
            event_type: 'trading', 'signal', 'health', or 'all'
            callback: Function to call with updated state
        """
        if event_type in self._subscribers:
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Unsubscribe from state changes"""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
            except ValueError:
                pass

    def _notify_subscribers(self, event_type: str, state: Any) -> None:
        """Notify all subscribers of state change"""
        for callback in self._subscribers.get(event_type, []):
            try:
                callback(state)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")

        # Also notify 'all' subscribers
        for callback in self._subscribers.get('all', []):
            try:
                callback(event_type, state)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")

    # Persistence

    def _persist_state(self) -> None:
        """Save state to disk"""
        try:
            state_file = self.persist_path / "state.json"
            data = {
                'trading': self._trading_state.to_dict(),
                'persisted_at': datetime.now(timezone.utc).isoformat()
            }

            with open(state_file, 'w') as f:
                json.dump(data, f, default=decimal_serializer, indent=2)

        except Exception as e:
            logger.error(f"Failed to persist state: {e}")

    def _load_state(self) -> None:
        """Load state from disk"""
        try:
            state_file = self.persist_path / "state.json"
            if not state_file.exists():
                return

            with open(state_file) as f:
                data = json.load(f)

            if 'trading' in data:
                trading_data = data['trading']
                for key, value in trading_data.items():
                    if hasattr(self._trading_state, key):
                        # Convert string Decimals back
                        if key in ['initial_capital', 'current_capital', 'total_profit',
                                   'total_fees', 'daily_pnl', 'max_drawdown', 'var_95']:
                            value = Decimal(value) if value else Decimal("0")
                        setattr(self._trading_state, key, value)

            logger.info("State loaded from disk")

        except Exception as e:
            logger.error(f"Failed to load state: {e}")

    # Snapshot Methods

    def create_snapshot(self) -> Dict:
        """Create full state snapshot"""
        with self._state_lock:
            return {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'trading': self._trading_state.to_dict(),
                'signal': asdict(self._signal_state),
                'health': asdict(self._system_health),
                'recent_trades': list(self._recent_trades),
                'recent_opportunities': list(self._recent_opportunities)
            }

    def get_dashboard_data(self) -> Dict:
        """Get data formatted for dashboard display"""
        with self._state_lock:
            return {
                'portfolio': {
                    'total_value': float(self._trading_state.current_capital),
                    'daily_pnl': float(self._trading_state.daily_pnl),
                    'daily_pnl_pct': float(
                        (self._trading_state.daily_pnl / self._trading_state.initial_capital * 100)
                        if self._trading_state.initial_capital > 0 else 0
                    ),
                    'total_profit': float(self._trading_state.total_profit),
                    'open_positions': len(self._trading_state.open_positions)
                },
                'sentiment': {
                    'market': {
                        'score': self._signal_state.market_sentiment,
                        'level': 'fear' if self._signal_state.market_sentiment < 40 else
                                'greed' if self._signal_state.market_sentiment > 60 else 'neutral',
                        'trend': self._signal_state.market_trend
                    },
                    **{asset: {'score': score, 'level': 'fear' if score < 40 else 'greed' if score > 60 else 'neutral'}
                       for asset, score in self._signal_state.asset_sentiment.items()}
                },
                'signals': self._signal_state.active_signals[-10:],
                'trades': list(self._recent_trades)[-10:],
                'status': 'live' if self._trading_state.mode == 'live' else 'paper',
                'system': {
                    'running': self._trading_state.running,
                    'mode': self._trading_state.mode,
                    'emergency_stop': self._trading_state.emergency_stop,
                    'exchanges_connected': self._trading_state.exchanges_connected,
                    'opportunities_detected': self._trading_state.opportunities_detected,
                    'opportunities_executed': self._trading_state.opportunities_executed,
                    'win_rate': self._trading_state.win_rate,
                    'sharpe_ratio': self._trading_state.sharpe_ratio
                },
                'health': {
                    'healthy': self._system_health.healthy,
                    'database': self._system_health.database_connected,
                    'redis': self._system_health.redis_connected,
                    'error_count': self._system_health.error_count_1h
                }
            }

    # Emergency Controls

    def activate_emergency_stop(self, reason: str) -> None:
        """Activate emergency stop"""
        with self._state_lock:
            self._trading_state.emergency_stop = True
            self._trading_state.emergency_reason = reason
            self._trading_state.running = False
            self._notify_subscribers('trading', self._trading_state)
            self._persist_state()
            logger.critical(f"EMERGENCY STOP ACTIVATED: {reason}")

    def deactivate_emergency_stop(self) -> None:
        """Deactivate emergency stop"""
        with self._state_lock:
            self._trading_state.emergency_stop = False
            self._trading_state.emergency_reason = ""
            self._notify_subscribers('trading', self._trading_state)
            self._persist_state()
            logger.info("Emergency stop deactivated")

    def is_trading_allowed(self) -> bool:
        """Check if trading is allowed"""
        with self._state_lock:
            return (
                self._trading_state.running and
                not self._trading_state.emergency_stop
            )


# Global accessor for convenience
def get_state_manager() -> StateManager:
    """Get global state manager instance"""
    return StateManager.get_instance()


__all__ = [
    'StateManager',
    'TradingState',
    'SignalState',
    'SystemHealth',
    'get_state_manager'
]
