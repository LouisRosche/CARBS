"""
Web Data

Data fetching and default values for dashboard.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)

# Import state manager for real data
try:
    from ..core.state_manager import StateManager, get_state_manager
    STATE_MANAGER_AVAILABLE = True
except ImportError:
    STATE_MANAGER_AVAILABLE = False


# Default fallback data when state manager is not available
DEFAULT_DATA = {
    "portfolio": {
        "total_value": 100.00,
        "daily_pnl": 0.00,
        "daily_pnl_pct": 0.00,
        "open_positions": 0,
        "total_profit": 0.00
    },
    "sentiment": {
        "market": {"score": 50, "level": "neutral", "trend": "stable"},
        "btc": {"score": 50, "level": "neutral", "trend": "stable"},
        "eth": {"score": 50, "level": "neutral", "trend": "stable"},
        "sol": {"score": 50, "level": "neutral", "trend": "stable"}
    },
    "signals": [],
    "trades": [],
    "status": "paper",
    "system": {
        "running": False,
        "mode": "paper",
        "emergency_stop": False,
        "exchanges_connected": [],
        "opportunities_detected": 0,
        "opportunities_executed": 0,
        "win_rate": 0.0,
        "sharpe_ratio": 0.0
    },
    "health": {
        "healthy": True,
        "database": False,
        "redis": False,
        "error_count": 0
    }
}

# For backwards compatibility
MOCK_DATA = DEFAULT_DATA


def get_dashboard_data() -> Dict:
    """
    Get dashboard data from state manager or return defaults

    This function bridges the state manager to the web dashboard,
    providing real-time data when available.
    """
    if STATE_MANAGER_AVAILABLE:
        try:
            state_mgr = get_state_manager()
            data = state_mgr.get_dashboard_data()

            # Ensure all expected keys exist with defaults
            result = DEFAULT_DATA.copy()
            result.update(data)
            return result
        except Exception as e:
            logger.warning(f"Failed to get data from state manager: {e}")
            return DEFAULT_DATA
    else:
        return DEFAULT_DATA
