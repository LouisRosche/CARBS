"""
Notification Models

Alert dataclass and related models.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict

from .enums import AlertPriority, AlertType


@dataclass
class Alert:
    """Alert message"""
    alert_id: str
    alert_type: AlertType
    priority: AlertPriority
    title: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data: Dict[str, Any] = field(default_factory=dict)
    delivered: bool = False
    retry_count: int = 0
