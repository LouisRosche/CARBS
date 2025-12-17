"""
Backtest Enums

Timeframe and other enumerations for backtesting.
"""

from enum import Enum


class TimeFrame(Enum):
    """Candlestick timeframes"""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"
