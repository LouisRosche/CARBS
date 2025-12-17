"""
Rate Limiter

Token bucket rate limiter for exchange API calls.
"""

import asyncio
import time


class RateLimiter:
    """
    Token bucket rate limiter

    Ensures we don't exceed exchange API limits
    """

    def __init__(self, requests_per_second: float = 10):
        self.rate = requests_per_second
        self.tokens = requests_per_second
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait for rate limit token"""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1
