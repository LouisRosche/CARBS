"""
Signal Service

Main service orchestrating signal generation.
"""

import asyncio
import logging
from pathlib import Path
from typing import Callable, Dict, List

from .enums import SentimentLevel
from .models import TradingSignal
from .aggregator import SentimentAggregator
from .generator import SignalGenerator

logger = logging.getLogger(__name__)


class SignalService:
    """
    Main service orchestrating signal generation

    Runs continuously, updating sentiment and generating signals.
    """

    def __init__(
        self,
        data_dir: Path = None,
        alert_callback: Callable = None,
        update_interval: int = 300  # 5 minutes
    ):
        self.data_dir = data_dir or Path("data/signals")
        self.alert_callback = alert_callback
        self.update_interval = update_interval

        self.aggregator = SentimentAggregator(data_dir=self.data_dir)
        self.generator = SignalGenerator(
            aggregator=self.aggregator,
            alert_callback=alert_callback
        )

        self._running = False
        self._task = None

    async def start(self):
        """Start the signal service"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Signal service started")

    async def stop(self):
        """Stop the signal service"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Signal service stopped")

    async def _run_loop(self):
        """Main service loop"""
        while self._running:
            try:
                # Generate signals for main assets
                signals = await self.generator.generate_signals(
                    assets=["BTC", "ETH", "SOL"],
                    include_market=True
                )

                if signals:
                    logger.info(f"Generated {len(signals)} signals")
                    for signal in signals:
                        logger.info(
                            f"  {signal.asset}: {signal.signal_type.value} "
                            f"(confidence: {signal.confidence:.0%})"
                        )

            except Exception as e:
                logger.error(f"Error in signal loop: {e}")

            await asyncio.sleep(self.update_interval)

    async def get_current_sentiment(self) -> Dict:
        """Get current sentiment summary"""
        await self.aggregator.update_all_sources()

        summary = {}
        for asset in ["MARKET", "BTC", "ETH", "SOL"]:
            level = self.aggregator.get_sentiment_level(asset)
            momentum = self.aggregator.get_sentiment_momentum(asset)
            history = self.aggregator._sentiment_history.get(asset, [])

            summary[asset] = {
                "level": level.value,
                "score": history[-1].score if history else None,
                "momentum": momentum,
                "trend": "improving" if momentum > 0.5 else "declining" if momentum < -0.5 else "stable"
            }

        return summary

    def get_signals(self) -> List[TradingSignal]:
        """Get active trading signals"""
        return self.generator.get_active_signals()


def create_signal_service(
    data_dir: Path = None,
    alert_callback: Callable = None
) -> SignalService:
    """Create and configure signal service"""
    return SignalService(
        data_dir=data_dir,
        alert_callback=alert_callback
    )
