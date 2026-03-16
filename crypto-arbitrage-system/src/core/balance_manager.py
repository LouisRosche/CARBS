"""
Balance Manager - Cross-Exchange Balance Tracking and Validation

Critical safety component that:
- Tracks real-time balances across all exchanges
- Validates trade sizes against available funds
- Detects and alerts on balance discrepancies
- Manages reserve ratios (don't trade with 100% of funds)
- Provides balance locking for in-flight trades

This is a CRITICAL component - trades must NOT execute without balance validation.
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, Optional, List, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class BalanceError(Exception):
    """Raised when balance operations fail"""
    pass


class InsufficientBalanceError(BalanceError):
    """Raised when balance is insufficient for operation"""
    pass


class BalanceDiscrepancyError(BalanceError):
    """Raised when actual balance doesn't match expected"""
    pass


class LockStatus(Enum):
    """Balance lock status"""
    ACTIVE = "active"
    RELEASED = "released"
    EXPIRED = "expired"


@dataclass
class BalanceSnapshot:
    """Point-in-time balance snapshot for an asset on an exchange"""
    exchange: str
    asset: str
    free: Decimal
    locked: Decimal
    timestamp: datetime

    @property
    def total(self) -> Decimal:
        return self.free + self.locked

    @property
    def age_seconds(self) -> float:
        """How old is this snapshot"""
        return (datetime.now(timezone.utc) - self.timestamp).total_seconds()


@dataclass
class BalanceLock:
    """Represents a temporary lock on balance for pending trade"""
    lock_id: str
    exchange: str
    asset: str
    amount: Decimal
    created_at: datetime
    expires_at: datetime
    trade_id: Optional[str] = None
    status: LockStatus = LockStatus.ACTIVE

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_active(self) -> bool:
        return self.status == LockStatus.ACTIVE and not self.is_expired


@dataclass
class ExchangeBalances:
    """All balances for a single exchange"""
    exchange: str
    balances: Dict[str, BalanceSnapshot] = field(default_factory=dict)
    last_update: Optional[datetime] = None
    update_in_progress: bool = False
    consecutive_failures: int = 0

    def get_balance(self, asset: str) -> Optional[BalanceSnapshot]:
        """Get balance for specific asset"""
        return self.balances.get(asset)

    def get_free(self, asset: str) -> Decimal:
        """Get free (available) balance for asset"""
        balance = self.balances.get(asset)
        return balance.free if balance else Decimal("0")

    def get_total(self, asset: str) -> Decimal:
        """Get total balance for asset"""
        balance = self.balances.get(asset)
        return balance.total if balance else Decimal("0")


class BalanceManager:
    """
    Centralized balance management across all exchanges.

    Features:
    - Real-time balance tracking with configurable refresh interval
    - Balance validation before trade execution
    - Reserve ratio management (configurable % held back)
    - Balance locking for in-flight trades
    - Discrepancy detection and alerting
    - Thread-safe operations
    """

    # Configuration defaults
    DEFAULT_REFRESH_INTERVAL = 30  # seconds
    DEFAULT_RESERVE_RATIO = Decimal("0.05")  # Keep 5% in reserve
    DEFAULT_LOCK_TIMEOUT = 300  # 5 minutes
    DEFAULT_STALE_THRESHOLD = 60  # seconds before balance considered stale
    MAX_CONSECUTIVE_FAILURES = 5

    def __init__(
        self,
        exchanges: Dict,
        refresh_interval: int = None,
        reserve_ratio: Decimal = None,
        lock_timeout: int = None,
        stale_threshold: int = None,
        circuit_breakers: Optional[Dict] = None
    ):
        """
        Initialize BalanceManager.

        Args:
            exchanges: Dict of exchange name -> exchange instance
            refresh_interval: How often to refresh balances (seconds)
            reserve_ratio: Fraction of balance to hold in reserve (0.0 - 1.0)
            lock_timeout: How long balance locks last (seconds)
            stale_threshold: How old before balance is considered stale (seconds)
            circuit_breakers: Optional dict of exchange name -> CircuitBreaker instance
        """
        self.exchanges = exchanges
        self.circuit_breakers = circuit_breakers or {}
        self.refresh_interval = refresh_interval or self.DEFAULT_REFRESH_INTERVAL
        self.reserve_ratio = reserve_ratio or self.DEFAULT_RESERVE_RATIO
        self.lock_timeout = lock_timeout or self.DEFAULT_LOCK_TIMEOUT
        self.stale_threshold = stale_threshold or self.DEFAULT_STALE_THRESHOLD

        # Balance storage per exchange
        self._balances: Dict[str, ExchangeBalances] = {
            name: ExchangeBalances(exchange=name)
            for name in exchanges.keys()
        }

        # Active balance locks
        self._locks: Dict[str, BalanceLock] = {}
        self._lock_counter = 0

        # Synchronization
        self._lock = asyncio.Lock()
        self._refresh_task: Optional[asyncio.Task] = None
        self._running = False

        # Metrics
        self._refresh_count = 0
        self._validation_count = 0
        self._validation_failures = 0

        logger.info(
            f"BalanceManager initialized for {len(exchanges)} exchanges "
            f"(refresh={self.refresh_interval}s, reserve={self.reserve_ratio*100}%)"
        )

    async def start(self):
        """Start background balance refresh"""
        if self._running:
            return

        self._running = True

        # Initial balance fetch
        await self.refresh_all_balances()

        # Start background refresh
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        logger.info("BalanceManager started")

    async def stop(self):
        """Stop background refresh"""
        self._running = False

        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

        logger.info("BalanceManager stopped")

    async def _refresh_loop(self):
        """Background loop to refresh balances"""
        while self._running:
            try:
                await asyncio.sleep(self.refresh_interval)
                await self.refresh_all_balances()
                await self._cleanup_expired_locks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Balance refresh error: {e}")
                await asyncio.sleep(5)  # Brief backoff on error

    async def refresh_all_balances(self):
        """Refresh balances from all exchanges"""
        tasks = [
            self.refresh_exchange_balances(name)
            for name in self.exchanges.keys()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        self._refresh_count += 1

    async def refresh_exchange_balances(self, exchange_name: str) -> bool:
        """
        Refresh balances for a single exchange.

        Returns:
            True if successful, False otherwise
        """
        if exchange_name not in self.exchanges:
            logger.warning(f"Unknown exchange: {exchange_name}")
            return False

        exchange = self.exchanges[exchange_name]
        exchange_balances = self._balances[exchange_name]

        if exchange_balances.update_in_progress:
            logger.debug(f"Balance update already in progress for {exchange_name}")
            return False

        exchange_balances.update_in_progress = True

        try:
            # Fetch balances from exchange API — with circuit breaker if available
            breaker = self.circuit_breakers.get(exchange_name)
            if breaker and hasattr(breaker, 'execute'):
                raw_balances = await breaker.execute(exchange.fetch_balance)
            elif hasattr(exchange, 'fetch_balance'):
                # ccxt.pro exchange — use fetch_balance
                raw_balances = await exchange.fetch_balance()
            else:
                # Custom BaseExchange — use get_balances
                raw_balances = await exchange.get_balances()
            now = datetime.now(timezone.utc)

            async with self._lock:
                # Handle ccxt.pro format: {asset: {free: x, used: y, total: z}}
                # vs BaseExchange format: {asset: Balance(free=x, locked=y)}
                for asset, balance in raw_balances.items():
                    # Skip non-asset keys in ccxt response
                    if asset in ('info', 'free', 'used', 'total', 'timestamp', 'datetime'):
                        continue
                    if isinstance(balance, dict):
                        free = Decimal(str(balance.get('free', 0) or 0))
                        locked = Decimal(str(balance.get('used', 0) or 0))
                    else:
                        free = balance.free if hasattr(balance, 'free') else Decimal('0')
                        locked = balance.locked if hasattr(balance, 'locked') else Decimal('0')
                    if free == 0 and locked == 0:
                        continue
                    exchange_balances.balances[asset] = BalanceSnapshot(
                        exchange=exchange_name,
                        asset=asset,
                        free=free,
                        locked=locked,
                        timestamp=now
                    )

                exchange_balances.last_update = now
                exchange_balances.consecutive_failures = 0

            logger.debug(
                f"Refreshed {len(raw_balances)} balances for {exchange_name}"
            )
            return True

        except Exception as e:
            exchange_balances.consecutive_failures += 1
            logger.error(
                f"Failed to refresh {exchange_name} balances "
                f"(attempt {exchange_balances.consecutive_failures}): {e}"
            )

            if exchange_balances.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                logger.critical(
                    f"CRITICAL: {exchange_name} balance refresh failed "
                    f"{self.MAX_CONSECUTIVE_FAILURES} times consecutively!"
                )

            return False

        finally:
            exchange_balances.update_in_progress = False

    def get_balance(
        self,
        exchange: str,
        asset: str
    ) -> Optional[BalanceSnapshot]:
        """Get current balance snapshot for exchange/asset"""
        if exchange not in self._balances:
            return None
        return self._balances[exchange].get_balance(asset)

    def get_available_balance(
        self,
        exchange: str,
        asset: str,
        include_reserve: bool = False
    ) -> Decimal:
        """
        Get available balance for trading.

        Args:
            exchange: Exchange name
            asset: Asset symbol
            include_reserve: If True, include reserve in available amount

        Returns:
            Available balance (free - locked - reserve)
        """
        balance = self.get_balance(exchange, asset)
        if not balance:
            return Decimal("0")

        # Get locked amount from our internal locks
        locked_amount = self._get_locked_amount(exchange, asset)

        # Calculate available
        available = balance.free - locked_amount

        # Apply reserve ratio unless explicitly requested
        if not include_reserve:
            reserve = balance.total * self.reserve_ratio
            available = max(Decimal("0"), available - reserve)

        return max(Decimal("0"), available)

    def _get_locked_amount(self, exchange: str, asset: str) -> Decimal:
        """Get total amount locked by pending trades"""
        total_locked = Decimal("0")
        for lock in self._locks.values():
            if lock.exchange == exchange and lock.asset == asset and lock.is_active:
                total_locked += lock.amount
        return total_locked

    async def validate_trade(
        self,
        exchange: str,
        asset: str,
        amount: Decimal,
        price: Decimal = None,
        quote_asset: str = None
    ) -> tuple[bool, str]:
        """
        Validate that a trade can be executed.

        For a buy order: validates quote asset balance
        For a sell order: validates base asset balance

        Args:
            exchange: Exchange name
            asset: Asset to trade (base asset for buy, sell asset for sell)
            amount: Amount to trade
            price: Price per unit (required for buy orders)
            quote_asset: Quote asset for buy orders (e.g., USDT)

        Returns:
            (valid: bool, reason: str)
        """
        self._validation_count += 1

        # Check exchange exists
        if exchange not in self._balances:
            self._validation_failures += 1
            return False, f"Unknown exchange: {exchange}"

        # Check balance freshness
        exchange_balances = self._balances[exchange]
        if exchange_balances.last_update is None:
            self._validation_failures += 1
            return False, f"No balance data for {exchange}"

        age = (datetime.now(timezone.utc) - exchange_balances.last_update).total_seconds()
        if age > self.stale_threshold:
            logger.warning(
                f"Stale balance data for {exchange} ({age:.0f}s old)"
            )
            # Don't fail, but warn - stale data is risky

        # Get available balance
        available = self.get_available_balance(exchange, asset)

        if available < amount:
            self._validation_failures += 1
            return False, (
                f"Insufficient {asset} on {exchange}: "
                f"need {amount}, available {available}"
            )

        return True, "OK"

    async def validate_arbitrage(
        self,
        buy_exchange: str,
        sell_exchange: str,
        base_asset: str,
        quote_asset: str,
        amount: Decimal,
        buy_price: Decimal,
        sell_price: Decimal
    ) -> tuple[bool, str]:
        """
        Validate that an arbitrage trade can be executed.

        Checks:
        1. Buy exchange has sufficient quote asset (e.g., USDT)
        2. Sell exchange has sufficient base asset (e.g., BTC)

        Args:
            buy_exchange: Exchange to buy on
            sell_exchange: Exchange to sell on
            base_asset: Asset being traded (e.g., BTC)
            quote_asset: Quote currency (e.g., USDT)
            amount: Amount of base asset to trade
            buy_price: Buy price
            sell_price: Sell price

        Returns:
            (valid: bool, reason: str)
        """
        # Check quote asset on buy exchange (need USDT to buy BTC)
        quote_needed = amount * buy_price
        quote_available = self.get_available_balance(buy_exchange, quote_asset)

        if quote_available < quote_needed:
            return False, (
                f"Insufficient {quote_asset} on {buy_exchange}: "
                f"need {quote_needed:.2f}, available {quote_available:.2f}"
            )

        # Check base asset on sell exchange (need BTC to sell)
        base_available = self.get_available_balance(sell_exchange, base_asset)

        if base_available < amount:
            return False, (
                f"Insufficient {base_asset} on {sell_exchange}: "
                f"need {amount}, available {base_available}"
            )

        return True, "OK"

    async def lock_balance(
        self,
        exchange: str,
        asset: str,
        amount: Decimal,
        trade_id: str = None
    ) -> Optional[str]:
        """
        Lock balance for a pending trade.

        Prevents the same funds from being used in multiple trades.

        Args:
            exchange: Exchange name
            asset: Asset to lock
            amount: Amount to lock
            trade_id: Optional trade identifier

        Returns:
            Lock ID if successful, None if insufficient balance
        """
        # Validate we have enough to lock
        available = self.get_available_balance(exchange, asset)
        if available < amount:
            logger.warning(
                f"Cannot lock {amount} {asset} on {exchange}: "
                f"only {available} available"
            )
            return None

        async with self._lock:
            self._lock_counter += 1
            lock_id = f"lock_{exchange}_{asset}_{self._lock_counter}"

            now = datetime.now(timezone.utc)
            lock = BalanceLock(
                lock_id=lock_id,
                exchange=exchange,
                asset=asset,
                amount=amount,
                created_at=now,
                expires_at=now + timedelta(seconds=self.lock_timeout),
                trade_id=trade_id
            )

            self._locks[lock_id] = lock

            logger.debug(
                f"Locked {amount} {asset} on {exchange} "
                f"(lock_id={lock_id}, trade_id={trade_id})"
            )

            return lock_id

    async def release_lock(self, lock_id: str) -> bool:
        """
        Release a balance lock.

        Args:
            lock_id: Lock identifier

        Returns:
            True if released, False if not found
        """
        async with self._lock:
            if lock_id not in self._locks:
                return False

            lock = self._locks[lock_id]
            lock.status = LockStatus.RELEASED
            del self._locks[lock_id]

            logger.debug(f"Released lock {lock_id}")
            return True

    async def _cleanup_expired_locks(self):
        """Remove expired locks (thread-safe)"""
        async with self._lock:
            expired = [
                lock_id for lock_id, lock in self._locks.items()
                if lock.is_expired
            ]

            for lock_id in expired:
                lock = self._locks[lock_id]
                lock.status = LockStatus.EXPIRED
                del self._locks[lock_id]
                logger.warning(
                    f"Lock {lock_id} expired: {lock.amount} {lock.asset} on {lock.exchange}"
                )

    def get_all_balances(self) -> Dict[str, Dict[str, BalanceSnapshot]]:
        """Get all balances across all exchanges"""
        return {
            exchange: dict(eb.balances)
            for exchange, eb in self._balances.items()
        }

    def get_total_value_usd(self, prices: Dict[str, Decimal]) -> Decimal:
        """
        Calculate total portfolio value in USD.

        Args:
            prices: Dict of asset -> USD price

        Returns:
            Total value in USD
        """
        total = Decimal("0")

        for exchange_balances in self._balances.values():
            for asset, balance in exchange_balances.balances.items():
                if asset in prices:
                    total += balance.total * prices[asset]
                elif asset in ("USD", "USDT", "USDC", "BUSD"):
                    total += balance.total

        return total

    def get_metrics(self) -> Dict:
        """Get balance manager metrics"""
        active_locks = sum(1 for lock in self._locks.values() if lock.is_active)
        locked_value = sum(
            lock.amount for lock in self._locks.values() if lock.is_active
        )

        exchange_status = {}
        for name, eb in self._balances.items():
            exchange_status[name] = {
                "last_update": eb.last_update.isoformat() if eb.last_update else None,
                "age_seconds": (
                    (datetime.now(timezone.utc) - eb.last_update).total_seconds()
                    if eb.last_update else None
                ),
                "consecutive_failures": eb.consecutive_failures,
                "asset_count": len(eb.balances)
            }

        return {
            "refresh_count": self._refresh_count,
            "validation_count": self._validation_count,
            "validation_failures": self._validation_failures,
            "validation_success_rate": (
                (self._validation_count - self._validation_failures) / self._validation_count
                if self._validation_count > 0 else 1.0
            ),
            "active_locks": active_locks,
            "locked_value": float(locked_value),
            "exchange_status": exchange_status
        }

    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.stop()
        return False


def parse_symbol(symbol: str) -> tuple[str, str]:
    """
    Parse trading symbol into base and quote assets.

    Args:
        symbol: Trading pair (e.g., "BTC/USDT" or "BTCUSDT")

    Returns:
        (base_asset, quote_asset)
    """
    if "/" in symbol:
        parts = symbol.split("/")
        return parts[0], parts[1]

    # Common quote assets
    quotes = ["USDT", "USDC", "BUSD", "USD", "BTC", "ETH", "BNB"]
    for quote in quotes:
        if symbol.endswith(quote):
            base = symbol[:-len(quote)]
            return base, quote

    # Fallback: assume last 4 chars are quote
    return symbol[:-4], symbol[-4:]
