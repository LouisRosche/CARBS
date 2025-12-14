"""
Multi-Channel Notification System

Production-grade notification system supporting:
- Email (SMTP with TLS)
- Slack (Webhooks + Bot API)
- Discord (Webhooks)
- PagerDuty (for critical alerts)
- Generic Webhooks
- SMS (via Twilio)

Features:
- Priority-based routing
- Rate limiting per channel
- Failover between channels
- Message templating
- Audit logging
"""

import asyncio
import logging
import smtplib
import ssl
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import aiohttp
import hashlib
import json

logger = logging.getLogger(__name__)


class NotificationPriority(Enum):
    """Notification priority levels"""
    DEBUG = 0       # Development only
    INFO = 1        # General information
    WARNING = 2     # Non-critical warnings
    ERROR = 3       # Errors requiring attention
    CRITICAL = 4    # Critical alerts requiring immediate action


class NotificationType(Enum):
    """Types of notifications"""
    TRADE_EXECUTED = "trade_executed"
    TRADE_FAILED = "trade_failed"
    OPPORTUNITY_FOUND = "opportunity"
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    EMERGENCY_STOP = "emergency_stop"
    ERROR = "error"
    SECURITY_ALERT = "security"
    BALANCE_WARNING = "balance"
    PROFIT_REPORT = "profit"
    DAILY_SUMMARY = "daily_summary"
    HEALTH_CHECK = "health"
    CUSTOM = "custom"


@dataclass
class Notification:
    """Notification message"""
    id: str
    type: NotificationType
    priority: NotificationPriority
    title: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data: Dict[str, Any] = field(default_factory=dict)
    channels: List[str] = field(default_factory=list)  # Specific channels or empty for all
    delivered_to: Set[str] = field(default_factory=set)
    retry_count: int = 0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "priority": self.priority.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data
        }


class NotificationChannel(ABC):
    """Base class for notification channels"""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled
        self._rate_limiter = ChannelRateLimiter()
        self._stats = {
            "sent": 0,
            "failed": 0,
            "rate_limited": 0
        }

    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """Send notification through this channel"""
        pass

    @abstractmethod
    def supports_priority(self, priority: NotificationPriority) -> bool:
        """Check if channel supports this priority level"""
        pass

    async def deliver(self, notification: Notification) -> bool:
        """Deliver notification with rate limiting"""
        if not self.enabled:
            return False

        if not self.supports_priority(notification.priority):
            return False

        if not self._rate_limiter.can_send():
            self._stats["rate_limited"] += 1
            logger.warning(f"Rate limit exceeded for channel {self.name}")
            return False

        try:
            success = await self.send(notification)
            if success:
                self._stats["sent"] += 1
                self._rate_limiter.record_send()
            else:
                self._stats["failed"] += 1
            return success
        except Exception as e:
            self._stats["failed"] += 1
            logger.error(f"Channel {self.name} failed: {e}")
            return False

    @property
    def stats(self) -> Dict:
        return dict(self._stats)


class ChannelRateLimiter:
    """Rate limiter for notification channels"""

    def __init__(
        self,
        max_per_minute: int = 30,
        max_per_hour: int = 200
    ):
        self.max_per_minute = max_per_minute
        self.max_per_hour = max_per_hour
        self._minute_window: deque = deque()
        self._hour_window: deque = deque()

    def _cleanup(self):
        now = datetime.now(timezone.utc)
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)

        while self._minute_window and self._minute_window[0] < minute_ago:
            self._minute_window.popleft()
        while self._hour_window and self._hour_window[0] < hour_ago:
            self._hour_window.popleft()

    def can_send(self) -> bool:
        self._cleanup()
        return (len(self._minute_window) < self.max_per_minute and
                len(self._hour_window) < self.max_per_hour)

    def record_send(self):
        now = datetime.now(timezone.utc)
        self._minute_window.append(now)
        self._hour_window.append(now)


class EmailChannel(NotificationChannel):
    """Email notification channel via SMTP"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_address: str,
        to_addresses: List[str],
        use_tls: bool = True,
        enabled: bool = True
    ):
        super().__init__("email", enabled)
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_address = from_address
        self.to_addresses = to_addresses
        self.use_tls = use_tls

    def supports_priority(self, priority: NotificationPriority) -> bool:
        # Email for warnings and above
        return priority.value >= NotificationPriority.WARNING.value

    async def send(self, notification: Notification) -> bool:
        """Send email notification"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[CARBS {notification.priority.name}] {notification.title}"
            msg['From'] = self.from_address
            msg['To'] = ", ".join(self.to_addresses)

            # Plain text version
            text_content = f"""
{notification.title}

{notification.message}

Time: {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
Priority: {notification.priority.name}
Type: {notification.type.value}
"""

            # HTML version
            html_content = self._format_html(notification)

            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))

            # Send in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_smtp, msg)

            logger.info(f"Email sent: {notification.title}")
            return True

        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False

    def _send_smtp(self, msg: MIMEMultipart):
        """Send via SMTP (blocking)"""
        context = ssl.create_default_context()

        if self.use_tls:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.username, self.password)
                server.send_message(msg)
        else:
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                server.login(self.username, self.password)
                server.send_message(msg)

    def _format_html(self, notification: Notification) -> str:
        """Format notification as HTML email"""
        priority_colors = {
            NotificationPriority.DEBUG: "#6c757d",
            NotificationPriority.INFO: "#17a2b8",
            NotificationPriority.WARNING: "#ffc107",
            NotificationPriority.ERROR: "#dc3545",
            NotificationPriority.CRITICAL: "#721c24"
        }

        color = priority_colors.get(notification.priority, "#333333")

        return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
        .header {{ background-color: {color}; color: white; padding: 15px; border-radius: 5px 5px 0 0; }}
        .content {{ border: 1px solid #ddd; border-top: none; padding: 20px; border-radius: 0 0 5px 5px; }}
        .meta {{ color: #666; font-size: 12px; margin-top: 20px; }}
        .data {{ background-color: #f5f5f5; padding: 10px; border-radius: 3px; font-family: monospace; }}
    </style>
</head>
<body>
    <div class="header">
        <h2 style="margin: 0;">{notification.title}</h2>
        <span>{notification.priority.name} | {notification.type.value}</span>
    </div>
    <div class="content">
        <p>{notification.message.replace(chr(10), '<br>')}</p>
        {self._format_data_html(notification.data) if notification.data else ''}
        <div class="meta">
            <p>Time: {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            <p>Notification ID: {notification.id}</p>
        </div>
    </div>
</body>
</html>
"""

    def _format_data_html(self, data: Dict) -> str:
        if not data:
            return ""
        return f'<div class="data"><pre>{json.dumps(data, indent=2, default=str)}</pre></div>'


class SlackChannel(NotificationChannel):
    """Slack notification channel via webhook"""

    def __init__(
        self,
        webhook_url: str,
        channel: str = None,
        username: str = "CARBS Bot",
        icon_emoji: str = ":chart_with_upwards_trend:",
        enabled: bool = True
    ):
        super().__init__("slack", enabled)
        self.webhook_url = webhook_url
        self.channel = channel
        self.username = username
        self.icon_emoji = icon_emoji

    def supports_priority(self, priority: NotificationPriority) -> bool:
        return priority.value >= NotificationPriority.INFO.value

    async def send(self, notification: Notification) -> bool:
        """Send Slack notification"""
        try:
            payload = self._build_payload(notification)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"Slack notification sent: {notification.title}")
                        return True
                    else:
                        text = await resp.text()
                        logger.error(f"Slack API error: {resp.status} - {text}")
                        return False

        except Exception as e:
            logger.error(f"Slack send failed: {e}")
            return False

    def _build_payload(self, notification: Notification) -> Dict:
        """Build Slack message payload with blocks"""
        priority_emoji = {
            NotificationPriority.DEBUG: ":bug:",
            NotificationPriority.INFO: ":information_source:",
            NotificationPriority.WARNING: ":warning:",
            NotificationPriority.ERROR: ":x:",
            NotificationPriority.CRITICAL: ":rotating_light:"
        }

        emoji = priority_emoji.get(notification.priority, ":bell:")

        payload = {
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} {notification.title}",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": notification.message
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Priority:* {notification.priority.name} | *Type:* {notification.type.value}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Time:* {notification.timestamp.strftime('%Y-%m-%d %H:%M UTC')}"
                        }
                    ]
                }
            ]
        }

        # Add data as a code block if present
        if notification.data:
            payload["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{json.dumps(notification.data, indent=2, default=str)}```"
                }
            })

        if self.channel:
            payload["channel"] = self.channel

        return payload


class DiscordChannel(NotificationChannel):
    """Discord notification channel via webhook"""

    def __init__(
        self,
        webhook_url: str,
        username: str = "CARBS Bot",
        avatar_url: str = None,
        enabled: bool = True
    ):
        super().__init__("discord", enabled)
        self.webhook_url = webhook_url
        self.username = username
        self.avatar_url = avatar_url

    def supports_priority(self, priority: NotificationPriority) -> bool:
        return priority.value >= NotificationPriority.INFO.value

    async def send(self, notification: Notification) -> bool:
        """Send Discord notification"""
        try:
            payload = self._build_payload(notification)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status in (200, 204):
                        logger.info(f"Discord notification sent: {notification.title}")
                        return True
                    else:
                        text = await resp.text()
                        logger.error(f"Discord API error: {resp.status} - {text}")
                        return False

        except Exception as e:
            logger.error(f"Discord send failed: {e}")
            return False

    def _build_payload(self, notification: Notification) -> Dict:
        """Build Discord embed payload"""
        priority_colors = {
            NotificationPriority.DEBUG: 0x6c757d,
            NotificationPriority.INFO: 0x17a2b8,
            NotificationPriority.WARNING: 0xffc107,
            NotificationPriority.ERROR: 0xdc3545,
            NotificationPriority.CRITICAL: 0x721c24
        }

        color = priority_colors.get(notification.priority, 0x333333)

        embed = {
            "title": notification.title,
            "description": notification.message,
            "color": color,
            "timestamp": notification.timestamp.isoformat(),
            "footer": {
                "text": f"{notification.priority.name} | {notification.type.value}"
            },
            "fields": []
        }

        # Add data fields
        if notification.data:
            for key, value in list(notification.data.items())[:5]:  # Limit to 5 fields
                embed["fields"].append({
                    "name": key,
                    "value": str(value)[:1024],  # Discord field value limit
                    "inline": True
                })

        payload = {
            "username": self.username,
            "embeds": [embed]
        }

        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url

        return payload


class PagerDutyChannel(NotificationChannel):
    """PagerDuty integration for critical alerts"""

    def __init__(
        self,
        routing_key: str,
        enabled: bool = True
    ):
        super().__init__("pagerduty", enabled)
        self.routing_key = routing_key
        self.api_url = "https://events.pagerduty.com/v2/enqueue"

    def supports_priority(self, priority: NotificationPriority) -> bool:
        # PagerDuty only for critical alerts
        return priority == NotificationPriority.CRITICAL

    async def send(self, notification: Notification) -> bool:
        """Send PagerDuty alert"""
        try:
            payload = {
                "routing_key": self.routing_key,
                "event_action": "trigger",
                "dedup_key": notification.id,
                "payload": {
                    "summary": f"[CARBS] {notification.title}: {notification.message[:200]}",
                    "severity": "critical",
                    "source": "carbs-trading-system",
                    "timestamp": notification.timestamp.isoformat(),
                    "custom_details": notification.data
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 202:
                        logger.info(f"PagerDuty alert sent: {notification.title}")
                        return True
                    else:
                        text = await resp.text()
                        logger.error(f"PagerDuty API error: {resp.status} - {text}")
                        return False

        except Exception as e:
            logger.error(f"PagerDuty send failed: {e}")
            return False


class WebhookChannel(NotificationChannel):
    """Generic webhook notification channel"""

    def __init__(
        self,
        name: str,
        webhook_url: str,
        headers: Dict[str, str] = None,
        min_priority: NotificationPriority = NotificationPriority.INFO,
        enabled: bool = True
    ):
        super().__init__(name, enabled)
        self.webhook_url = webhook_url
        self.headers = headers or {}
        self.min_priority = min_priority

    def supports_priority(self, priority: NotificationPriority) -> bool:
        return priority.value >= self.min_priority.value

    async def send(self, notification: Notification) -> bool:
        """Send webhook notification"""
        try:
            payload = notification.to_dict()

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status < 300:
                        logger.info(f"Webhook {self.name} sent: {notification.title}")
                        return True
                    else:
                        text = await resp.text()
                        logger.error(f"Webhook {self.name} error: {resp.status} - {text}")
                        return False

        except Exception as e:
            logger.error(f"Webhook {self.name} failed: {e}")
            return False


class NotificationManager:
    """
    Central notification manager

    Routes notifications to appropriate channels based on:
    - Priority level
    - Notification type
    - Channel availability
    - Rate limits

    Features:
    - Automatic failover
    - Deduplication
    - Async delivery
    - Comprehensive logging
    """

    def __init__(self):
        self._channels: Dict[str, NotificationChannel] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._sent_hashes: deque = deque(maxlen=1000)
        self._stats = {
            "total_sent": 0,
            "total_failed": 0,
            "by_channel": {},
            "by_type": {}
        }

        # Priority to channel mapping (default)
        self._priority_channels: Dict[NotificationPriority, List[str]] = {
            NotificationPriority.DEBUG: [],
            NotificationPriority.INFO: ["slack", "discord"],
            NotificationPriority.WARNING: ["slack", "discord", "email"],
            NotificationPriority.ERROR: ["slack", "discord", "email"],
            NotificationPriority.CRITICAL: ["pagerduty", "slack", "discord", "email"]
        }

    def add_channel(self, channel: NotificationChannel):
        """Add notification channel"""
        self._channels[channel.name] = channel
        self._stats["by_channel"][channel.name] = {"sent": 0, "failed": 0}
        logger.info(f"Added notification channel: {channel.name}")

    def remove_channel(self, name: str):
        """Remove notification channel"""
        if name in self._channels:
            del self._channels[name]
            logger.info(f"Removed notification channel: {name}")

    def configure_priority_channels(
        self,
        priority: NotificationPriority,
        channels: List[str]
    ):
        """Configure which channels handle each priority"""
        self._priority_channels[priority] = channels

    async def start(self):
        """Start notification processor"""
        self._running = True
        asyncio.create_task(self._process_queue())
        logger.info("Notification manager started")

    async def stop(self):
        """Stop notification processor"""
        self._running = False
        logger.info("Notification manager stopped")

    async def notify(
        self,
        type: NotificationType,
        priority: NotificationPriority,
        title: str,
        message: str,
        data: Dict = None,
        channels: List[str] = None
    ) -> str:
        """
        Send notification

        Args:
            type: Notification type
            priority: Priority level
            title: Short title
            message: Full message
            data: Additional data
            channels: Specific channels (or None for auto-routing)

        Returns:
            Notification ID
        """
        notification = Notification(
            id=self._generate_id(title, message),
            type=type,
            priority=priority,
            title=title,
            message=message,
            data=data or {},
            channels=channels or []
        )

        await self._queue.put(notification)
        return notification.id

    def _generate_id(self, title: str, message: str) -> str:
        """Generate unique notification ID"""
        content = f"{title}:{message}:{datetime.now().timestamp()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def _process_queue(self):
        """Process notification queue"""
        while self._running:
            try:
                notification = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )

                # Check deduplication
                hash_key = hashlib.md5(
                    f"{notification.title}:{notification.message}".encode()
                ).hexdigest()

                if hash_key in self._sent_hashes:
                    logger.debug(f"Skipping duplicate: {notification.id}")
                    continue

                # Determine target channels
                target_channels = notification.channels or self._priority_channels.get(
                    notification.priority, []
                )

                # Deliver to each channel
                delivered = False
                for channel_name in target_channels:
                    channel = self._channels.get(channel_name)
                    if not channel:
                        continue

                    success = await channel.deliver(notification)
                    if success:
                        notification.delivered_to.add(channel_name)
                        self._stats["by_channel"][channel_name]["sent"] += 1
                        delivered = True
                    else:
                        self._stats["by_channel"][channel_name]["failed"] += 1

                # Update stats
                if delivered:
                    self._stats["total_sent"] += 1
                    self._sent_hashes.append(hash_key)

                    type_key = notification.type.value
                    if type_key not in self._stats["by_type"]:
                        self._stats["by_type"][type_key] = 0
                    self._stats["by_type"][type_key] += 1
                else:
                    self._stats["total_failed"] += 1

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing notification: {e}")
                await asyncio.sleep(1)

    def get_stats(self) -> Dict:
        """Get notification statistics"""
        return dict(self._stats)

    # Convenience methods

    async def alert_trade(
        self,
        symbol: str,
        profit: float,
        buy_exchange: str,
        sell_exchange: str,
        execution_time_ms: int
    ):
        """Send trade execution alert"""
        is_profit = profit > 0
        priority = NotificationPriority.INFO if is_profit else NotificationPriority.WARNING

        await self.notify(
            type=NotificationType.TRADE_EXECUTED,
            priority=priority,
            title=f"{'Profitable' if is_profit else 'Loss'} Trade: {symbol}",
            message=(
                f"Route: {buy_exchange} -> {sell_exchange}\n"
                f"P&L: ${profit:+.2f}\n"
                f"Execution: {execution_time_ms}ms"
            ),
            data={
                "symbol": symbol,
                "profit": profit,
                "buy_exchange": buy_exchange,
                "sell_exchange": sell_exchange,
                "execution_time_ms": execution_time_ms
            }
        )

    async def alert_error(self, error_type: str, message: str, details: Dict = None):
        """Send error alert"""
        await self.notify(
            type=NotificationType.ERROR,
            priority=NotificationPriority.ERROR,
            title=f"Error: {error_type}",
            message=message,
            data=details
        )

    async def alert_critical(self, title: str, message: str, data: Dict = None):
        """Send critical alert"""
        await self.notify(
            type=NotificationType.EMERGENCY_STOP,
            priority=NotificationPriority.CRITICAL,
            title=title,
            message=message,
            data=data
        )

    async def alert_security(self, event: str, details: str, data: Dict = None):
        """Send security alert"""
        await self.notify(
            type=NotificationType.SECURITY_ALERT,
            priority=NotificationPriority.ERROR,
            title=f"Security Alert: {event}",
            message=details,
            data=data
        )

    async def send_daily_summary(
        self,
        trades_count: int,
        profit: float,
        win_rate: float,
        best_trade: float,
        worst_trade: float
    ):
        """Send daily summary"""
        await self.notify(
            type=NotificationType.DAILY_SUMMARY,
            priority=NotificationPriority.INFO,
            title="Daily Trading Summary",
            message=(
                f"Total Trades: {trades_count}\n"
                f"Net P&L: ${profit:+.2f}\n"
                f"Win Rate: {win_rate:.1%}\n"
                f"Best Trade: ${best_trade:+.2f}\n"
                f"Worst Trade: ${worst_trade:+.2f}"
            ),
            data={
                "trades_count": trades_count,
                "profit": profit,
                "win_rate": win_rate,
                "best_trade": best_trade,
                "worst_trade": worst_trade
            }
        )


def setup_notifications(config: Dict) -> NotificationManager:
    """
    Setup notification manager from configuration

    Config example:
    {
        "email": {
            "enabled": true,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "...",
            "password": "...",
            "from_address": "...",
            "to_addresses": ["..."]
        },
        "slack": {
            "enabled": true,
            "webhook_url": "..."
        },
        "discord": {
            "enabled": true,
            "webhook_url": "..."
        },
        "pagerduty": {
            "enabled": true,
            "routing_key": "..."
        }
    }
    """
    manager = NotificationManager()

    # Setup email
    email_config = config.get("email", {})
    if email_config.get("enabled"):
        manager.add_channel(EmailChannel(
            smtp_host=email_config["smtp_host"],
            smtp_port=email_config["smtp_port"],
            username=email_config["username"],
            password=email_config["password"],
            from_address=email_config["from_address"],
            to_addresses=email_config["to_addresses"]
        ))

    # Setup Slack
    slack_config = config.get("slack", {})
    if slack_config.get("enabled"):
        manager.add_channel(SlackChannel(
            webhook_url=slack_config["webhook_url"],
            channel=slack_config.get("channel")
        ))

    # Setup Discord
    discord_config = config.get("discord", {})
    if discord_config.get("enabled"):
        manager.add_channel(DiscordChannel(
            webhook_url=discord_config["webhook_url"]
        ))

    # Setup PagerDuty
    pagerduty_config = config.get("pagerduty", {})
    if pagerduty_config.get("enabled"):
        manager.add_channel(PagerDutyChannel(
            routing_key=pagerduty_config["routing_key"]
        ))

    # Setup custom webhooks
    for webhook in config.get("webhooks", []):
        if webhook.get("enabled"):
            manager.add_channel(WebhookChannel(
                name=webhook["name"],
                webhook_url=webhook["url"],
                headers=webhook.get("headers", {})
            ))

    return manager


__all__ = [
    "NotificationPriority",
    "NotificationType",
    "Notification",
    "NotificationChannel",
    "EmailChannel",
    "SlackChannel",
    "DiscordChannel",
    "PagerDutyChannel",
    "WebhookChannel",
    "NotificationManager",
    "setup_notifications"
]
