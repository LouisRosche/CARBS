"""
Signal Manager

Config-aware wrapper around SignalService for use by AdvancedArbitrageBot.
Accepts a TradingConfig and exposes the async interface that advanced_main expects.
"""

import logging
from pathlib import Path
from typing import Dict, List

from .service import SignalService
from .models import TradingSignal

logger = logging.getLogger(__name__)


class SignalManager:
    """
    Manages signal generation lifecycle with config-based initialization.

    This bridges the gap between the config-driven AdvancedArbitrageBot and
    the lower-level SignalService.
    """

    def __init__(self, config):
        """
        Initialize from a TradingConfig (or any object with signals/data_dir attrs).

        Args:
            config: Trading configuration object or dict
        """
        data_dir = Path("data/signals")
        update_interval = 300

        if hasattr(config, 'data_dir'):
            data_dir = Path(config.data_dir) / "signals"
        if hasattr(config, 'signal_update_interval'):
            update_interval = config.signal_update_interval

        self._service = SignalService(
            data_dir=data_dir,
            update_interval=update_interval,
        )

    async def start(self):
        """Start the signal generation loop."""
        await self._service.start()

    async def stop(self):
        """Stop signal generation."""
        await self._service.stop()

    async def get_active_signals(self) -> List[Dict]:
        """
        Return active signals as dicts (the format advanced_main expects).

        Returns:
            List of signal dicts with keys: symbol, direction, confidence, source
        """
        signals: List[TradingSignal] = self._service.get_signals()
        return [
            {
                "symbol": s.asset,
                "direction": s.signal_type.value if hasattr(s.signal_type, 'value') else str(s.signal_type),
                "confidence": s.confidence,
                "source": s.source if hasattr(s, 'source') else "sentiment",
            }
            for s in signals
        ]

    async def get_current_sentiment(self) -> Dict:
        """Delegate to underlying service."""
        return await self._service.get_current_sentiment()
