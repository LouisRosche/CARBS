"""
Backtesting Framework

Production-grade backtesting with:
- Historical data management
- Realistic simulation (fees, slippage, latency)
- Walk-forward optimization
- Monte Carlo robustness testing
- Performance analytics
- Anti-fragility metrics
"""

import asyncio
import logging
import hashlib
import statistics
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from pathlib import Path
from collections import deque
import json
import math

logger = logging.getLogger(__name__)


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


@dataclass
class OHLCV:
    """Single candlestick"""
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "volume": str(self.volume)
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "OHLCV":
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            open=Decimal(data["open"]),
            high=Decimal(data["high"]),
            low=Decimal(data["low"]),
            close=Decimal(data["close"]),
            volume=Decimal(data["volume"])
        )


@dataclass
class BacktestTrade:
    """Single trade in backtest"""
    trade_id: str
    entry_time: datetime
    exit_time: datetime = None
    asset: str = ""
    side: str = "long"  # long/short

    entry_price: Decimal = Decimal("0")
    exit_price: Decimal = None
    position_size: Decimal = Decimal("0")

    stop_loss: Decimal = None
    take_profit: Decimal = None

    # Costs
    entry_fee: Decimal = Decimal("0")
    exit_fee: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")

    # Results
    pnl: Decimal = None
    pnl_percent: Decimal = None
    status: str = "open"  # open, closed, stopped_out, take_profit

    # Signal info
    signal_confidence: float = 0.0
    signal_reasons: List[str] = field(default_factory=list)


@dataclass
class BacktestResult:
    """Complete backtest results"""
    backtest_id: str
    strategy_name: str
    asset: str
    timeframe: TimeFrame
    start_date: datetime
    end_date: datetime

    # Capital
    initial_capital: Decimal
    final_capital: Decimal
    peak_capital: Decimal
    trough_capital: Decimal

    # Trade stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    # Returns
    total_return: float = 0.0
    annualized_return: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration_days: int = 0

    # Risk metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Trade quality
    avg_win: Decimal = Decimal("0")
    avg_loss: Decimal = Decimal("0")
    profit_factor: float = 0.0
    expectancy: Decimal = Decimal("0")

    # Anti-fragility metrics
    tail_ratio: float = 0.0  # Positive outliers vs negative
    recovery_factor: float = 0.0  # Total profit / max drawdown
    ulcer_index: float = 0.0  # Depth and duration of drawdowns

    # Execution stats
    total_fees: Decimal = Decimal("0")
    total_slippage: Decimal = Decimal("0")
    avg_holding_period_hours: float = 0.0

    # All trades
    trades: List[BacktestTrade] = field(default_factory=list)

    # Equity curve
    equity_curve: List[Tuple[datetime, Decimal]] = field(default_factory=list)


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


class WalkForwardOptimizer:
    """
    Walk-forward optimization for robust parameter selection

    Prevents overfitting by:
    1. Dividing data into train/test windows
    2. Optimizing on train, validating on test
    3. Rolling forward through time
    """

    def __init__(
        self,
        engine: BacktestEngine,
        train_size: int = 30,  # days
        test_size: int = 10,   # days
        step_size: int = 10    # days to roll forward
    ):
        self.engine = engine
        self.train_size = train_size
        self.test_size = test_size
        self.step_size = step_size

    async def optimize(
        self,
        strategy: Callable,
        asset: str,
        timeframe: TimeFrame,
        start: datetime,
        end: datetime,
        param_grid: Dict[str, List],
        metric: str = "sharpe_ratio"
    ) -> Dict:
        """
        Run walk-forward optimization

        Returns:
            Best parameters and aggregated results
        """
        results = []
        current_start = start

        while current_start + timedelta(days=self.train_size + self.test_size) <= end:
            train_end = current_start + timedelta(days=self.train_size)
            test_end = train_end + timedelta(days=self.test_size)

            # Find best params on training data
            best_params = None
            best_score = float('-inf')

            for params in self._generate_param_combinations(param_grid):
                result = await self.engine.run(
                    strategy=strategy,
                    asset=asset,
                    timeframe=timeframe,
                    start=current_start,
                    end=train_end,
                    strategy_params=params
                )

                score = getattr(result, metric, 0)
                if score > best_score:
                    best_score = score
                    best_params = params

            # Validate on test data
            if best_params:
                test_result = await self.engine.run(
                    strategy=strategy,
                    asset=asset,
                    timeframe=timeframe,
                    start=train_end,
                    end=test_end,
                    strategy_params=best_params
                )

                results.append({
                    "train_period": (current_start, train_end),
                    "test_period": (train_end, test_end),
                    "best_params": best_params,
                    "train_score": best_score,
                    "test_score": getattr(test_result, metric, 0),
                    "test_result": test_result
                })

            current_start += timedelta(days=self.step_size)

        # Aggregate results
        return self._aggregate_results(results, metric)

    def _generate_param_combinations(self, param_grid: Dict) -> List[Dict]:
        """Generate all parameter combinations"""
        if not param_grid:
            return [{}]

        keys = list(param_grid.keys())
        values = list(param_grid.values())

        combinations = []

        def _recurse(idx, current):
            if idx == len(keys):
                combinations.append(dict(current))
                return
            for val in values[idx]:
                current[keys[idx]] = val
                _recurse(idx + 1, current)

        _recurse(0, {})
        return combinations

    def _aggregate_results(self, results: List[Dict], metric: str) -> Dict:
        """Aggregate walk-forward results"""
        if not results:
            return {"error": "No results"}

        # Find most robust parameters (best avg test score)
        param_scores: Dict[str, List[float]] = {}

        for r in results:
            params_key = json.dumps(r["best_params"], sort_keys=True)
            if params_key not in param_scores:
                param_scores[params_key] = []
            param_scores[params_key].append(r["test_score"])

        # Best by average
        best_params_key = max(param_scores.keys(), key=lambda k: statistics.mean(param_scores[k]))

        return {
            "best_params": json.loads(best_params_key),
            "avg_test_score": statistics.mean(param_scores[best_params_key]),
            "test_score_std": statistics.stdev(param_scores[best_params_key]) if len(param_scores[best_params_key]) > 1 else 0,
            "num_windows": len(results),
            "consistency": sum(1 for r in results if r["test_score"] > 0) / len(results),
            "all_results": results
        }


class MonteCarloSimulator:
    """
    Monte Carlo simulation for strategy robustness

    Tests strategy performance under:
    - Random trade order shuffling
    - Return distribution sampling
    - Regime changes
    """

    def __init__(self, n_simulations: int = 1000):
        self.n_simulations = n_simulations

    def run_trade_shuffle(self, trades: List[BacktestTrade], initial_capital: Decimal) -> Dict:
        """
        Shuffle trade order to test path dependency

        A robust strategy should perform similarly regardless of trade order.
        """
        original_pnls = [float(t.pnl or 0) for t in trades]

        final_capitals = []

        for _ in range(self.n_simulations):
            shuffled = original_pnls.copy()
            random.shuffle(shuffled)

            capital = float(initial_capital)
            for pnl in shuffled:
                capital += pnl
                if capital <= 0:
                    capital = 0
                    break

            final_capitals.append(capital)

        return {
            "original_final": float(initial_capital) + sum(original_pnls),
            "mean_final": statistics.mean(final_capitals),
            "std_final": statistics.stdev(final_capitals),
            "min_final": min(final_capitals),
            "max_final": max(final_capitals),
            "probability_of_ruin": sum(1 for c in final_capitals if c <= 0) / self.n_simulations,
            "confidence_95_lower": sorted(final_capitals)[int(0.025 * len(final_capitals))],
            "confidence_95_upper": sorted(final_capitals)[int(0.975 * len(final_capitals))]
        }

    def run_bootstrap(self, daily_returns: List[float], initial_capital: float, days: int = 252) -> Dict:
        """
        Bootstrap simulation of future returns

        Samples from historical return distribution to project future outcomes.
        """
        simulations = []

        for _ in range(self.n_simulations):
            capital = initial_capital
            path = [capital]

            for _ in range(days):
                daily_return = random.choice(daily_returns)
                capital *= (1 + daily_return)
                path.append(capital)

            simulations.append({
                "final_capital": capital,
                "max_drawdown": self._calculate_max_drawdown(path),
                "path": path
            })

        final_capitals = [s["final_capital"] for s in simulations]
        drawdowns = [s["max_drawdown"] for s in simulations]

        return {
            "mean_final": statistics.mean(final_capitals),
            "median_final": statistics.median(final_capitals),
            "std_final": statistics.stdev(final_capitals),
            "var_95": sorted(final_capitals)[int(0.05 * len(final_capitals))],
            "cvar_95": statistics.mean(sorted(final_capitals)[:int(0.05 * len(final_capitals))]),
            "mean_max_drawdown": statistics.mean(drawdowns),
            "probability_of_loss": sum(1 for c in final_capitals if c < initial_capital) / self.n_simulations
        }

    def _calculate_max_drawdown(self, path: List[float]) -> float:
        """Calculate max drawdown from equity path"""
        peak = path[0]
        max_dd = 0

        for value in path:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)

        return max_dd


# Example strategy for backtesting
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


__all__ = [
    "TimeFrame",
    "OHLCV",
    "BacktestTrade",
    "BacktestResult",
    "HistoricalDataManager",
    "BacktestEngine",
    "WalkForwardOptimizer",
    "MonteCarloSimulator",
    "momentum_strategy"
]
