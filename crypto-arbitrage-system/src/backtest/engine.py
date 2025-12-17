"""
Backtest Engine

Core backtesting engine with realistic simulation.
"""

import hashlib
import logging
import math
import statistics
from datetime import datetime
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Tuple

from .enums import TimeFrame
from .models import OHLCV, BacktestTrade, BacktestResult
from .data_manager import HistoricalDataManager

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Core backtesting engine

    Features:
    - Event-driven simulation
    - Realistic execution model
    - Slippage and fee simulation
    - Position tracking
    """

    def __init__(
        self,
        initial_capital: Decimal = Decimal("10000"),
        fee_rate: Decimal = Decimal("0.001"),  # 0.1%
        slippage_rate: Decimal = Decimal("0.0005"),  # 0.05%
        data_manager: HistoricalDataManager = None
    ):
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
        self.data_manager = data_manager or HistoricalDataManager()

        # State during backtest
        self._capital = initial_capital
        self._positions: Dict[str, BacktestTrade] = {}
        self._trades: List[BacktestTrade] = []
        self._equity_curve: List[Tuple[datetime, Decimal]] = []

    async def run(
        self,
        strategy: Callable,
        asset: str,
        timeframe: TimeFrame,
        start: datetime,
        end: datetime,
        strategy_params: Dict = None
    ) -> BacktestResult:
        """
        Run backtest

        Args:
            strategy: Function that takes (candles, position, params) and returns signal
            asset: Asset to trade
            timeframe: Candlestick timeframe
            start: Start date
            end: End date
            strategy_params: Strategy-specific parameters
        """
        strategy_params = strategy_params or {}

        # Reset state
        self._capital = self.initial_capital
        self._positions = {}
        self._trades = []
        self._equity_curve = [(start, self.initial_capital)]

        # Fetch historical data
        candles = await self.data_manager.fetch_historical_data(
            asset, timeframe, start, end
        )

        if not candles:
            raise ValueError(f"No historical data available for {asset}")

        logger.info(f"Running backtest on {len(candles)} candles")

        # Simulate trading
        lookback = strategy_params.get("lookback", 50)

        for i in range(lookback, len(candles)):
            current_candle = candles[i]
            history = candles[max(0, i - lookback):i + 1]

            # Check for stop loss / take profit first
            self._check_exits(current_candle)

            # Get current position
            position = self._positions.get(asset)

            # Generate signal
            signal = await strategy(
                candles=history,
                current=current_candle,
                position=position,
                capital=self._capital,
                params=strategy_params
            )

            # Execute signal
            if signal:
                await self._execute_signal(
                    signal=signal,
                    asset=asset,
                    candle=current_candle
                )

            # Update equity curve
            equity = self._calculate_equity(current_candle, asset)
            self._equity_curve.append((current_candle.timestamp, equity))

        # Close any remaining positions
        if candles:
            self._close_all_positions(candles[-1])

        # Calculate results
        return self._calculate_results(
            strategy_name=strategy.__name__,
            asset=asset,
            timeframe=timeframe,
            start=start,
            end=end
        )

    def _check_exits(self, candle: OHLCV):
        """Check for stop loss or take profit hits"""
        for asset, trade in list(self._positions.items()):
            if trade.side == "long":
                # Stop loss hit
                if trade.stop_loss and candle.low <= trade.stop_loss:
                    self._close_position(asset, trade.stop_loss, candle.timestamp, "stopped_out")
                # Take profit hit
                elif trade.take_profit and candle.high >= trade.take_profit:
                    self._close_position(asset, trade.take_profit, candle.timestamp, "take_profit")
            else:  # short
                if trade.stop_loss and candle.high >= trade.stop_loss:
                    self._close_position(asset, trade.stop_loss, candle.timestamp, "stopped_out")
                elif trade.take_profit and candle.low <= trade.take_profit:
                    self._close_position(asset, trade.take_profit, candle.timestamp, "take_profit")

    async def _execute_signal(
        self,
        signal: Dict,
        asset: str,
        candle: OHLCV
    ):
        """Execute trading signal"""
        action = signal.get("action")  # buy, sell, close

        if action == "close" and asset in self._positions:
            self._close_position(asset, candle.close, candle.timestamp, "signal")

        elif action == "buy" and asset not in self._positions:
            # Calculate position size
            size_pct = signal.get("size_pct", 0.1)  # 10% default
            position_value = self._capital * Decimal(str(size_pct))

            # Apply slippage to entry
            slippage = candle.close * self.slippage_rate
            entry_price = candle.close + slippage

            # Calculate fees
            fee = position_value * self.fee_rate

            # Create trade
            trade = BacktestTrade(
                trade_id=hashlib.sha256(
                    f"{asset}:{candle.timestamp}".encode()
                ).hexdigest()[:12],
                entry_time=candle.timestamp,
                asset=asset,
                side="long",
                entry_price=entry_price,
                position_size=position_value / entry_price,
                stop_loss=signal.get("stop_loss"),
                take_profit=signal.get("take_profit"),
                entry_fee=fee,
                slippage=slippage * (position_value / entry_price),
                signal_confidence=signal.get("confidence", 0.5),
                signal_reasons=signal.get("reasons", [])
            )

            self._positions[asset] = trade
            self._capital -= (position_value + fee)

        elif action == "sell" and asset not in self._positions:
            # Short position (if supported)
            pass

    def _close_position(
        self,
        asset: str,
        exit_price: Decimal,
        exit_time: datetime,
        status: str
    ):
        """Close position and record trade"""
        trade = self._positions.pop(asset, None)
        if not trade:
            return

        # Apply slippage
        slippage = exit_price * self.slippage_rate
        actual_exit = exit_price - slippage if trade.side == "long" else exit_price + slippage

        # Calculate P&L
        if trade.side == "long":
            pnl = (actual_exit - trade.entry_price) * trade.position_size
        else:
            pnl = (trade.entry_price - actual_exit) * trade.position_size

        # Exit fee
        exit_value = actual_exit * trade.position_size
        exit_fee = exit_value * self.fee_rate

        # Net P&L
        net_pnl = pnl - trade.entry_fee - exit_fee

        # Update trade
        trade.exit_time = exit_time
        trade.exit_price = actual_exit
        trade.exit_fee = exit_fee
        trade.pnl = net_pnl
        trade.pnl_percent = (net_pnl / (trade.entry_price * trade.position_size)) * 100
        trade.status = status

        self._trades.append(trade)

        # Return capital
        self._capital += (exit_value - exit_fee)

    def _close_all_positions(self, candle: OHLCV):
        """Close all open positions at end of backtest"""
        for asset in list(self._positions.keys()):
            self._close_position(asset, candle.close, candle.timestamp, "closed")

    def _calculate_equity(self, candle: OHLCV, asset: str) -> Decimal:
        """Calculate current equity including open positions"""
        equity = self._capital

        if asset in self._positions:
            trade = self._positions[asset]
            if trade.side == "long":
                unrealized = (candle.close - trade.entry_price) * trade.position_size
            else:
                unrealized = (trade.entry_price - candle.close) * trade.position_size
            equity += (trade.entry_price * trade.position_size) + unrealized

        return equity

    def _calculate_results(
        self,
        strategy_name: str,
        asset: str,
        timeframe: TimeFrame,
        start: datetime,
        end: datetime
    ) -> BacktestResult:
        """Calculate comprehensive backtest results"""
        result = BacktestResult(
            backtest_id=hashlib.sha256(
                f"{strategy_name}:{asset}:{start}:{end}".encode()
            ).hexdigest()[:12],
            strategy_name=strategy_name,
            asset=asset,
            timeframe=timeframe,
            start_date=start,
            end_date=end,
            initial_capital=self.initial_capital,
            final_capital=self._capital,
            trades=self._trades,
            equity_curve=self._equity_curve
        )

        if not self._trades:
            return result

        # Trade statistics
        result.total_trades = len(self._trades)
        result.winning_trades = sum(1 for t in self._trades if t.pnl and t.pnl > 0)
        result.losing_trades = sum(1 for t in self._trades if t.pnl and t.pnl < 0)
        result.win_rate = result.winning_trades / result.total_trades if result.total_trades > 0 else 0

        # Returns
        result.total_return = float((self._capital - self.initial_capital) / self.initial_capital * 100)

        # Annualized return
        days = (end - start).days
        if days > 0:
            result.annualized_return = ((float(self._capital / self.initial_capital) ** (365 / days)) - 1) * 100

        # Equity curve analysis
        equities = [float(e[1]) for e in self._equity_curve]
        result.peak_capital = Decimal(str(max(equities)))
        result.trough_capital = Decimal(str(min(equities)))

        # Max drawdown
        peak = equities[0]
        max_dd = 0
        dd_start = 0
        max_dd_duration = 0

        for i, eq in enumerate(equities):
            if eq > peak:
                peak = eq
                dd_start = i
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
                max_dd_duration = i - dd_start

        result.max_drawdown = max_dd * 100
        result.max_drawdown_duration_days = max_dd_duration

        # Daily returns for risk metrics
        daily_returns = []
        for i in range(1, len(equities)):
            daily_returns.append((equities[i] - equities[i-1]) / equities[i-1])

        if daily_returns:
            avg_return = statistics.mean(daily_returns)
            std_return = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0.0001

            # Sharpe ratio (assuming 0% risk-free rate)
            result.sharpe_ratio = (avg_return * 252) / (std_return * math.sqrt(252)) if std_return > 0 else 0

            # Sortino ratio (downside deviation only)
            downside_returns = [r for r in daily_returns if r < 0]
            if downside_returns:
                downside_std = statistics.stdev(downside_returns)
                result.sortino_ratio = (avg_return * 252) / (downside_std * math.sqrt(252)) if downside_std > 0 else 0

        # Calmar ratio
        if result.max_drawdown > 0:
            result.calmar_ratio = result.annualized_return / result.max_drawdown

        # Trade quality
        wins = [float(t.pnl) for t in self._trades if t.pnl and t.pnl > 0]
        losses = [abs(float(t.pnl)) for t in self._trades if t.pnl and t.pnl < 0]

        if wins:
            result.avg_win = Decimal(str(statistics.mean(wins)))
        if losses:
            result.avg_loss = Decimal(str(statistics.mean(losses)))

        # Profit factor
        total_wins = sum(wins)
        total_losses = sum(losses)
        result.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        # Expectancy
        if result.total_trades > 0:
            result.expectancy = Decimal(str(
                (result.win_rate * float(result.avg_win or 0)) -
                ((1 - result.win_rate) * float(result.avg_loss or 0))
            ))

        # Anti-fragility metrics
        # Tail ratio: ratio of positive to negative outliers
        if daily_returns:
            sorted_returns = sorted(daily_returns)
            bottom_5 = sorted_returns[:max(1, len(sorted_returns) // 20)]
            top_5 = sorted_returns[-max(1, len(sorted_returns) // 20):]
            avg_bottom = abs(statistics.mean(bottom_5)) if bottom_5 else 0.0001
            avg_top = statistics.mean(top_5) if top_5 else 0
            result.tail_ratio = avg_top / avg_bottom if avg_bottom > 0 else 0

        # Recovery factor
        if result.max_drawdown > 0:
            result.recovery_factor = result.total_return / result.max_drawdown

        # Execution stats
        result.total_fees = sum(t.entry_fee + t.exit_fee for t in self._trades)
        result.total_slippage = sum(t.slippage for t in self._trades)

        # Average holding period
        holding_periods = []
        for t in self._trades:
            if t.exit_time:
                holding_periods.append((t.exit_time - t.entry_time).total_seconds() / 3600)
        if holding_periods:
            result.avg_holding_period_hours = statistics.mean(holding_periods)

        return result
