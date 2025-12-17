"""
Telegram Alert Manager

Main Telegram notification manager with security features.
"""

import asyncio
import hashlib
import logging
import os
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .enums import AlertPriority, AlertType
from .models import Alert
from .queue import RateLimitedQueue

logger = logging.getLogger(__name__)

# Telegram bot imports
try:
    from telegram import Bot
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("python-telegram-bot not installed. Telegram alerts disabled.")


class TelegramAlertManager:
    """
    Telegram alert manager with security features

    Features:
    - Rate-limited sending
    - Priority-based queuing
    - Message deduplication
    - Secure bot token storage
    - Chat ID verification
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        secrets_manager=None
    ):
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
        self._queue = RateLimitedQueue()
        self._running = False
        self._sent_hashes: deque = deque(maxlen=1000)

        # Alert settings
        self._settings = {
            'enabled': True,
            'min_priority': AlertPriority.LOW,
            'quiet_hours': None,
            'daily_summary_hour': 8,
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

        asyncio.create_task(self._process_queue())

        try:
            me = await self._bot.get_me()
            logger.info(f"Telegram bot connected: @{me.username}")

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

                if not self._queue.can_send():
                    await self._queue.enqueue(alert)
                    await asyncio.sleep(2)
                    continue

                alert_hash = self._hash_alert(alert)
                if alert_hash in self._sent_hashes:
                    logger.debug(f"Skipping duplicate alert: {alert.alert_id}")
                    continue

                if not self._should_send(alert):
                    continue

                success = await self._deliver_alert(alert)

                if success:
                    self._queue.record_send()
                    self._sent_hashes.append(alert_hash)
                    self._update_stats(alert, success=True)
                else:
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

        priority_order = [AlertPriority.LOW, AlertPriority.MEDIUM, AlertPriority.HIGH, AlertPriority.CRITICAL]
        min_priority = self._settings['min_priority']
        if priority_order.index(alert.priority) < priority_order.index(min_priority):
            return False

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
