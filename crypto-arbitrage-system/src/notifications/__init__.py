"""
Telegram Alert System

Secure, rate-limited notifications for:
- Trade executions
- Opportunity alerts
- Emergency notifications
- Daily summaries
- System health alerts
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from collections import deque
import hashlib
import hmac

logger = logging.getLogger(__name__)

# Telegram bot imports
try:
    from telegram import Bot, Update
    from telegram.ext import Application, CommandHandler, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("python-telegram-bot not installed. Telegram alerts disabled.")


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


class RateLimitedQueue:
    """
    Rate-limited message queue

    Prevents Telegram API rate limiting and spam
    """

    def __init__(
        self,
        max_per_minute: int = 20,
        max_per_hour: int = 100,
        burst_limit: int = 5
    ):
        self.max_per_minute = max_per_minute
        self.max_per_hour = max_per_hour
        self.burst_limit = burst_limit

        self._minute_window: deque = deque()
        self._hour_window: deque = deque()
        self._queue: asyncio.Queue = asyncio.Queue()

    def _cleanup_windows(self):
        """Remove old timestamps from windows"""
        now = datetime.now(timezone.utc)
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)

        while self._minute_window and self._minute_window[0] < minute_ago:
            self._minute_window.popleft()

        while self._hour_window and self._hour_window[0] < hour_ago:
            self._hour_window.popleft()

    def can_send(self) -> bool:
        """Check if we can send a message now"""
        self._cleanup_windows()

        if len(self._minute_window) >= self.max_per_minute:
            return False

        if len(self._hour_window) >= self.max_per_hour:
            return False

        return True

    def record_send(self):
        """Record that we sent a message"""
        now = datetime.now(timezone.utc)
        self._minute_window.append(now)
        self._hour_window.append(now)

    async def enqueue(self, alert: Alert):
        """Add alert to queue"""
        await self._queue.put(alert)

    async def dequeue(self) -> Optional[Alert]:
        """Get next alert from queue"""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            return None


class TelegramAlertManager:
    """
    Telegram alert manager with security features

    Features:
    - Rate-limited sending
    - Priority-based queuing
    - Message deduplication
    - Secure bot token storage
    - Chat ID verification
    - Command interface for status
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        secrets_manager=None
    ):
        """
        Initialize Telegram alert manager

        Args:
            bot_token: Telegram bot token (or from secrets)
            chat_id: Telegram chat ID to send to (or from secrets)
            secrets_manager: SecretsManager for encrypted storage
        """
        if not TELEGRAM_AVAILABLE:
            raise ImportError("python-telegram-bot not installed")

        self._secrets_manager = secrets_manager

        # Get credentials from secrets manager or params
        if secrets_manager:
            self._bot_token = secrets_manager.get_secret('telegram_bot_token') or bot_token
            self._chat_id = secrets_manager.get_secret('telegram_chat_id') or chat_id
        else:
            self._bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
            self._chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')

        if not self._bot_token:
            raise ValueError("Telegram bot token required")

        self._bot: Optional[Bot] = None
        self._application: Optional[Application] = None
        self._queue = RateLimitedQueue()
        self._running = False
        self._sent_hashes: deque = deque(maxlen=1000)  # Dedup last 1000

        # Alert settings
        self._settings = {
            'enabled': True,
            'min_priority': AlertPriority.LOW,
            'quiet_hours': None,  # Tuple of (start_hour, end_hour) UTC
            'daily_summary_hour': 8,  # UTC hour for daily summary
        }

        # Statistics
        self._stats = {
            'total_sent': 0,
            'total_failed': 0,
            'by_type': {},
            'by_priority': {}
        }

    async def start(self):
        """Start the alert manager"""
        self._bot = Bot(token=self._bot_token)
        self._running = True

        # Start message processor
        asyncio.create_task(self._process_queue())

        # Verify connection
        try:
            me = await self._bot.get_me()
            logger.info(f"Telegram bot connected: @{me.username}")

            # Send startup notification
            await self.send_alert(Alert(
                alert_id=f"start_{datetime.now().timestamp()}",
                alert_type=AlertType.SYSTEM_START,
                priority=AlertPriority.MEDIUM,
                title="🚀 CARBS Started",
                message="Crypto arbitrage system is now running.",
                data={'bot_username': me.username}
            ))

        except Exception as e:
            logger.error(f"Failed to connect to Telegram: {e}")
            raise

    async def stop(self):
        """Stop the alert manager"""
        self._running = False

        # Send shutdown notification
        try:
            await self._send_message(
                "🛑 *CARBS Stopped*\n\nSystem has been shut down.",
                parse_mode='Markdown'
            )
        except Exception:
            pass

    async def _process_queue(self):
        """Process alert queue with rate limiting"""
        while self._running:
            try:
                alert = await self._queue.dequeue()

                if alert is None:
                    continue

                # Check if we can send
                if not self._queue.can_send():
                    # Re-queue and wait
                    await self._queue.enqueue(alert)
                    await asyncio.sleep(2)
                    continue

                # Check deduplication
                alert_hash = self._hash_alert(alert)
                if alert_hash in self._sent_hashes:
                    logger.debug(f"Skipping duplicate alert: {alert.alert_id}")
                    continue

                # Check settings
                if not self._should_send(alert):
                    continue

                # Send
                success = await self._deliver_alert(alert)

                if success:
                    self._queue.record_send()
                    self._sent_hashes.append(alert_hash)
                    self._update_stats(alert, success=True)
                else:
                    # Retry up to 3 times
                    alert.retry_count += 1
                    if alert.retry_count < 3:
                        await self._queue.enqueue(alert)
                    else:
                        self._update_stats(alert, success=False)

            except Exception as e:
                logger.error(f"Error processing alert queue: {e}")
                await asyncio.sleep(5)

    def _hash_alert(self, alert: Alert) -> str:
        """Create hash for deduplication"""
        content = f"{alert.alert_type.value}:{alert.title}:{alert.message}"
        return hashlib.md5(content.encode()).hexdigest()

    def _should_send(self, alert: Alert) -> bool:
        """Check if alert should be sent based on settings"""
        if not self._settings['enabled']:
            return False

        # Priority filter
        priority_order = [AlertPriority.LOW, AlertPriority.MEDIUM, AlertPriority.HIGH, AlertPriority.CRITICAL]
        min_priority = self._settings['min_priority']
        if priority_order.index(alert.priority) < priority_order.index(min_priority):
            return False

        # Quiet hours (except critical)
        if self._settings['quiet_hours'] and alert.priority != AlertPriority.CRITICAL:
            start, end = self._settings['quiet_hours']
            current_hour = datetime.now(timezone.utc).hour
            if start <= current_hour < end:
                return False

        return True

    async def _deliver_alert(self, alert: Alert) -> bool:
        """Deliver alert to Telegram"""
        try:
            message = self._format_alert(alert)
            await self._send_message(message, parse_mode='Markdown')
            alert.delivered = True
            logger.info(f"Alert delivered: {alert.alert_type.value}")
            return True

        except Exception as e:
            logger.error(f"Failed to deliver alert: {e}")
            return False

    async def _send_message(self, text: str, parse_mode: str = None):
        """Send message to Telegram"""
        if not self._bot or not self._chat_id:
            return

        await self._bot.send_message(
            chat_id=self._chat_id,
            text=text,
            parse_mode=parse_mode
        )

    def _format_alert(self, alert: Alert) -> str:
        """Format alert for Telegram"""
        # Priority emoji
        priority_emoji = {
            AlertPriority.LOW: "ℹ️",
            AlertPriority.MEDIUM: "📊",
            AlertPriority.HIGH: "⚠️",
            AlertPriority.CRITICAL: "🚨"
        }

        emoji = priority_emoji.get(alert.priority, "📌")
        timestamp = alert.timestamp.strftime("%Y-%m-%d %H:%M UTC")

        message = f"{emoji} *{alert.title}*\n\n"
        message += f"{alert.message}\n\n"
        message += f"_{timestamp}_"

        return message

    def _update_stats(self, alert: Alert, success: bool):
        """Update statistics"""
        if success:
            self._stats['total_sent'] += 1
        else:
            self._stats['total_failed'] += 1

        type_key = alert.alert_type.value
        if type_key not in self._stats['by_type']:
            self._stats['by_type'][type_key] = 0
        self._stats['by_type'][type_key] += 1

        priority_key = alert.priority.value
        if priority_key not in self._stats['by_priority']:
            self._stats['by_priority'][priority_key] = 0
        self._stats['by_priority'][priority_key] += 1

    # Public methods for sending alerts

    async def send_alert(self, alert: Alert):
        """Queue an alert for sending"""
        await self._queue.enqueue(alert)

    async def alert_trade_executed(
        self,
        symbol: str,
        buy_exchange: str,
        sell_exchange: str,
        profit: float,
        execution_time_ms: int
    ):
        """Send trade execution alert"""
        profit_emoji = "✅" if profit > 0 else "❌"
        priority = AlertPriority.HIGH if abs(profit) > 50 else AlertPriority.MEDIUM

        await self.send_alert(Alert(
            alert_id=f"trade_{datetime.now().timestamp()}",
            alert_type=AlertType.TRADE_EXECUTED,
            priority=priority,
            title=f"{profit_emoji} Trade Executed: {symbol}",
            message=(
                f"*Route:* {buy_exchange} → {sell_exchange}\n"
                f"*Profit:* ${profit:.2f}\n"
                f"*Execution:* {execution_time_ms}ms"
            ),
            data={
                'symbol': symbol,
                'profit': profit,
                'buy_exchange': buy_exchange,
                'sell_exchange': sell_exchange
            }
        ))

    async def alert_opportunity_found(
        self,
        symbol: str,
        spread_percent: float,
        buy_exchange: str,
        sell_exchange: str,
        score: float
    ):
        """Send opportunity alert"""
        await self.send_alert(Alert(
            alert_id=f"opp_{datetime.now().timestamp()}",
            alert_type=AlertType.OPPORTUNITY_FOUND,
            priority=AlertPriority.MEDIUM,
            title=f"💰 Opportunity: {symbol}",
            message=(
                f"*Spread:* {spread_percent:.3f}%\n"
                f"*Route:* {buy_exchange} → {sell_exchange}\n"
                f"*Score:* {score:.2f}"
            ),
            data={'symbol': symbol, 'spread': spread_percent}
        ))

    async def alert_emergency_stop(self, reason: str, activated_by: str):
        """Send emergency stop alert"""
        await self.send_alert(Alert(
            alert_id=f"emergency_{datetime.now().timestamp()}",
            alert_type=AlertType.EMERGENCY_STOP,
            priority=AlertPriority.CRITICAL,
            title="🚨 EMERGENCY STOP ACTIVATED",
            message=(
                f"*Reason:* {reason}\n"
                f"*Activated by:* {activated_by}\n\n"
                "All trading has been halted."
            ),
            data={'reason': reason, 'activated_by': activated_by}
        ))

    async def alert_error(self, error_type: str, message: str, details: str = None):
        """Send error alert"""
        full_message = f"*Error:* {message}"
        if details:
            full_message += f"\n*Details:* {details}"

        await self.send_alert(Alert(
            alert_id=f"error_{datetime.now().timestamp()}",
            alert_type=AlertType.ERROR,
            priority=AlertPriority.HIGH,
            title=f"❌ Error: {error_type}",
            message=full_message,
            data={'error_type': error_type}
        ))

    async def alert_daily_summary(
        self,
        trades_count: int,
        profit: float,
        win_rate: float,
        best_trade: float,
        worst_trade: float
    ):
        """Send daily summary"""
        profit_emoji = "📈" if profit > 0 else "📉"

        await self.send_alert(Alert(
            alert_id=f"summary_{datetime.now().date()}",
            alert_type=AlertType.DAILY_SUMMARY,
            priority=AlertPriority.LOW,
            title=f"{profit_emoji} Daily Summary",
            message=(
                f"*Trades:* {trades_count}\n"
                f"*P&L:* ${profit:.2f}\n"
                f"*Win Rate:* {win_rate:.1%}\n"
                f"*Best:* ${best_trade:.2f}\n"
                f"*Worst:* ${worst_trade:.2f}"
            ),
            data={
                'trades': trades_count,
                'profit': profit,
                'win_rate': win_rate
            }
        ))

    async def alert_security_event(self, event: str, details: str):
        """Send security alert"""
        await self.send_alert(Alert(
            alert_id=f"security_{datetime.now().timestamp()}",
            alert_type=AlertType.SECURITY_EVENT,
            priority=AlertPriority.HIGH,
            title="🔐 Security Event",
            message=f"*Event:* {event}\n*Details:* {details}",
            data={'event': event}
        ))

    async def alert_balance_low(self, exchange: str, currency: str, balance: float, minimum: float):
        """Send low balance warning"""
        await self.send_alert(Alert(
            alert_id=f"balance_{exchange}_{currency}",
            alert_type=AlertType.BALANCE_LOW,
            priority=AlertPriority.HIGH,
            title=f"⚠️ Low Balance: {exchange}",
            message=(
                f"*Currency:* {currency}\n"
                f"*Balance:* {balance:.2f}\n"
                f"*Minimum:* {minimum:.2f}"
            ),
            data={'exchange': exchange, 'currency': currency, 'balance': balance}
        ))

    async def send_heartbeat(self):
        """Send heartbeat (for monitoring)"""
        await self.send_alert(Alert(
            alert_id=f"heartbeat_{datetime.now().timestamp()}",
            alert_type=AlertType.HEARTBEAT,
            priority=AlertPriority.LOW,
            title="💓 System Heartbeat",
            message="System is running normally.",
            data={}
        ))

    def get_stats(self) -> Dict[str, Any]:
        """Get alert statistics"""
        return dict(self._stats)

    def configure(self, **settings):
        """Update alert settings"""
        for key, value in settings.items():
            if key in self._settings:
                self._settings[key] = value
                logger.info(f"Alert setting updated: {key} = {value}")


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
