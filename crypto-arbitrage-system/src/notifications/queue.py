"""
Rate Limited Queue

Rate-limited message queue for Telegram API.
"""

import asyncio
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Optional

from .models import Alert


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
