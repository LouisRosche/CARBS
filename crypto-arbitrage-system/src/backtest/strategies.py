"""
Example Strategies

Example trading strategies for backtesting.
"""

from decimal import Decimal
from typing import Dict, List, Optional

from .models import OHLCV, BacktestTrade


async def momentum_strategy(
    candles: List[OHLCV],
    current: OHLCV,
    position: Optional[BacktestTrade],
    capital: Decimal,
    params: Dict
) -> Optional[Dict]:
    """
    Simple momentum strategy for testing

    Buy when price crosses above SMA
    Sell when price crosses below SMA
    """
    sma_period = params.get("sma_period", 20)
    stop_pct = params.get("stop_pct", 0.02)
    target_pct = params.get("target_pct", 0.04)

    if len(candles) < sma_period + 1:
        return None

    # Calculate SMA
    closes = [float(c.close) for c in candles[-sma_period:]]
    sma = sum(closes) / len(closes)

    prev_close = float(candles[-2].close)
    curr_close = float(current.close)

    # Entry signal
    if not position:
        if prev_close < sma and curr_close > sma:
            return {
                "action": "buy",
                "size_pct": 0.2,
                "stop_loss": current.close * Decimal(str(1 - stop_pct)),
                "take_profit": current.close * Decimal(str(1 + target_pct)),
                "confidence": 0.6,
                "reasons": ["Price crossed above SMA"]
            }

    # Exit signal
    elif position:
        if curr_close < sma:
            return {"action": "close"}

    return None
