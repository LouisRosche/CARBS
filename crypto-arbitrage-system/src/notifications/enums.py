"""
Notification Enums

Alert priority and type enumerations.
"""

from enum import Enum


class AlertPriority(Enum):
    """Alert priority levels"""
    LOW = "low"           # Info, daily summaries
    MEDIUM = "medium"     # Opportunities, normal trades
    HIGH = "high"         # Large trades, warnings
    CRITICAL = "critical" # Emergencies, errors, losses


class AlertType(Enum):
    """Types of alerts"""
    TRADE_EXECUTED = "trade_executed"
    TRADE_FAILED = "trade_failed"
    OPPORTUNITY_FOUND = "opportunity_found"
    DAILY_SUMMARY = "daily_summary"
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    EMERGENCY_STOP = "emergency_stop"
    ERROR = "error"
    SECURITY_EVENT = "security_event"
    BALANCE_LOW = "balance_low"
    PROFIT_MILESTONE = "profit_milestone"
    LOSS_WARNING = "loss_warning"
    HEARTBEAT = "heartbeat"
