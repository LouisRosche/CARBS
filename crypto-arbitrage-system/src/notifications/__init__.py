"""
Telegram Alert System

Secure, rate-limited notifications for:
- Trade executions
- Opportunity alerts
- Emergency notifications
- Daily summaries
- System health alerts

Module Structure:
- enums.py: AlertPriority, AlertType
- models.py: Alert dataclass
- queue.py: RateLimitedQueue
- manager.py: TelegramAlertManager
"""

import logging
from typing import Optional

from .enums import AlertPriority, AlertType
from .models import Alert
from .queue import RateLimitedQueue
from .manager import TelegramAlertManager

logger = logging.getLogger(__name__)

# Check for telegram availability
try:
    from telegram import Bot
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("python-telegram-bot not installed. Telegram alerts disabled.")


async def setup_telegram_alerts(secrets_manager=None) -> Optional[TelegramAlertManager]:
    """
    Setup Telegram alerts

    Returns:
        TelegramAlertManager or None if not configured
    """
    if not TELEGRAM_AVAILABLE:
        logger.warning("Telegram not available")
        return None

    try:
        manager = TelegramAlertManager(secrets_manager=secrets_manager)
        await manager.start()
        return manager
    except Exception as e:
        logger.error(f"Failed to setup Telegram alerts: {e}")
        return None


__all__ = [
    # Enums
    "AlertPriority",
    "AlertType",

    # Models
    "Alert",

    # Queue
    "RateLimitedQueue",

    # Manager
    "TelegramAlertManager",

    # Setup
    "setup_telegram_alerts",

    # Flags
    "TELEGRAM_AVAILABLE",
]
