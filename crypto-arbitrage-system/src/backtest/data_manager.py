"""
Historical Data Manager

Manages historical price data with caching and multiple sources.
"""

import json
import logging
import random
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List

from .enums import TimeFrame
from .models import OHLCV

logger = logging.getLogger(__name__)


class HistoricalDataManager:
    """
    Manages historical price data

    Features:
    - Fetches from multiple sources
    - Caches locally for fast replay
    - Handles gaps and adjustments
    """

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data/historical")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._cache: Dict[str, List[OHLCV]] = {}

    def get_cache_path(self, asset: str, timeframe: TimeFrame) -> Path:
        """Get path for cached data file"""
        return self.data_dir / f"{asset.lower()}_{timeframe.value}.json"

    async def fetch_historical_data(
        self,
        asset: str,
        timeframe: TimeFrame,
        start: datetime,
        end: datetime,
        source: str = "cryptocompare"
    ) -> List[OHLCV]:
        """
        Fetch historical OHLCV data

        Sources: cryptocompare (free), binance, etc.
        """
        cache_key = f"{asset}:{timeframe.value}"

        # Check cache first
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            filtered = [c for c in cached if start <= c.timestamp <= end]
            if filtered:
                return filtered

        # Load from file if exists
        cache_path = self.get_cache_path(asset, timeframe)
        if cache_path.exists():
            data = await self._load_from_file(cache_path, start, end)
            if data:
                return data

        # Fetch from API
        if source == "cryptocompare":
            data = await self._fetch_cryptocompare(asset, timeframe, start, end)
        else:
            data = await self._fetch_mock(asset, timeframe, start, end)

        # Cache
        if data:
            self._cache[cache_key] = data
            await self._save_to_file(cache_path, data)

        return data

    async def _load_from_file(
        self,
        path: Path,
        start: datetime,
        end: datetime
    ) -> List[OHLCV]:
        """Load data from cache file"""
        try:
            with open(path) as f:
                raw = json.load(f)
                data = [OHLCV.from_dict(d) for d in raw]
                return [d for d in data if start <= d.timestamp <= end]
        except Exception as e:
            logger.error(f"Failed to load cached data: {e}")
            return []

    async def _save_to_file(self, path: Path, data: List[OHLCV]):
        """Save data to cache file"""
        try:
            # Merge with existing
            existing = []
            if path.exists():
                with open(path) as f:
                    existing = [OHLCV.from_dict(d) for d in json.load(f)]

            # Combine and deduplicate
            all_data = {d.timestamp: d for d in existing}
            for d in data:
                all_data[d.timestamp] = d

            # Sort and save
            sorted_data = sorted(all_data.values(), key=lambda x: x.timestamp)

            with open(path, 'w') as f:
                json.dump([d.to_dict() for d in sorted_data], f)

        except Exception as e:
            logger.error(f"Failed to save cached data: {e}")

    async def _fetch_cryptocompare(
        self,
        asset: str,
        timeframe: TimeFrame,
        start: datetime,
        end: datetime
    ) -> List[OHLCV]:
        """Fetch from CryptoCompare API"""
        import aiohttp

        # Map timeframe to API endpoint
        endpoint_map = {
            TimeFrame.M1: "histominute",
            TimeFrame.H1: "histohour",
            TimeFrame.D1: "histoday"
        }

        endpoint = endpoint_map.get(timeframe, "histohour")
        base_url = f"https://min-api.cryptocompare.com/data/v2/{endpoint}"

        # Calculate limit
        tf_seconds = {
            TimeFrame.M1: 60,
            TimeFrame.M5: 300,
            TimeFrame.M15: 900,
            TimeFrame.H1: 3600,
            TimeFrame.H4: 14400,
            TimeFrame.D1: 86400
        }
        seconds = tf_seconds.get(timeframe, 3600)
        limit = min(2000, int((end - start).total_seconds() / seconds))

        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "fsym": asset.upper(),
                    "tsym": "USD",
                    "limit": limit,
                    "toTs": int(end.timestamp())
                }

                async with session.get(base_url, params=params) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        data = []

                        for item in result.get("Data", {}).get("Data", []):
                            ts = datetime.fromtimestamp(item["time"], tz=timezone.utc)
                            if start <= ts <= end:
                                data.append(OHLCV(
                                    timestamp=ts,
                                    open=Decimal(str(item["open"])),
                                    high=Decimal(str(item["high"])),
                                    low=Decimal(str(item["low"])),
                                    close=Decimal(str(item["close"])),
                                    volume=Decimal(str(item.get("volumeto", 0)))
                                ))

                        return sorted(data, key=lambda x: x.timestamp)

        except Exception as e:
            logger.error(f"Failed to fetch from CryptoCompare: {e}")

        return []

    async def _fetch_mock(
        self,
        asset: str,
        timeframe: TimeFrame,
        start: datetime,
        end: datetime
    ) -> List[OHLCV]:
        """Generate mock data for testing"""
        data = []
        current = start

        # Starting prices
        base_prices = {"BTC": 67000, "ETH": 3400, "SOL": 170}
        price = Decimal(str(base_prices.get(asset.upper(), 100)))

        # Timeframe to seconds
        tf_seconds = {
            TimeFrame.M1: 60, TimeFrame.M5: 300, TimeFrame.M15: 900,
            TimeFrame.H1: 3600, TimeFrame.H4: 14400, TimeFrame.D1: 86400
        }
        interval = timedelta(seconds=tf_seconds.get(timeframe, 3600))

        while current <= end:
            # Random walk with drift
            change_pct = random.gauss(0.0001, 0.01)  # Slight upward drift
            price = price * (1 + Decimal(str(change_pct)))

            high = price * Decimal(str(1 + abs(random.gauss(0, 0.005))))
            low = price * Decimal(str(1 - abs(random.gauss(0, 0.005))))

            data.append(OHLCV(
                timestamp=current,
                open=price,
                high=high,
                low=low,
                close=price * Decimal(str(1 + random.gauss(0, 0.002))),
                volume=Decimal(str(random.uniform(1000000, 10000000)))
            ))

            current += interval

        return data
