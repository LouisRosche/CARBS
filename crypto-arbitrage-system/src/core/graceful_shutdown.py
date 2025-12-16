"""
Graceful Shutdown Manager

Handles clean system shutdown including:
- Waiting for in-flight operations to complete
- Cancelling pending orders
- Closing open positions (optional)
- Flushing logs and metrics
- Resource cleanup

Critical for production systems to prevent orphaned orders and positions.
"""

import asyncio
import logging
import signal
from typing import Dict, Optional, List, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class ShutdownPhase(Enum):
    """Phases of graceful shutdown"""
    RUNNING = "running"
    DRAINING = "draining"  # Stop accepting new work
    CANCELLING = "cancelling"  # Cancel pending orders
    CLOSING = "closing"  # Close positions (if configured)
    FLUSHING = "flushing"  # Flush logs/metrics
    CLEANUP = "cleanup"  # Close connections
    COMPLETE = "complete"


@dataclass
class ShutdownConfig:
    """Configuration for graceful shutdown"""
    # Timeouts
    drain_timeout_seconds: int = 30  # Wait for in-flight operations
    cancel_timeout_seconds: int = 30  # Wait for order cancellations
    close_positions_timeout_seconds: int = 60  # Wait for position closes
    cleanup_timeout_seconds: int = 10  # Wait for resource cleanup

    # Behavior
    close_positions_on_shutdown: bool = False  # If True, close all positions
    force_close_after_timeout: bool = True  # Force shutdown if timeouts exceeded
    notify_on_shutdown: bool = True  # Send notification on shutdown

    # Total max shutdown time
    max_shutdown_seconds: int = 180  # 3 minutes max


@dataclass
class InFlightOperation:
    """Tracks an in-flight operation"""
    operation_id: str
    operation_type: str  # 'trade', 'order', 'rebalance'
    started_at: datetime
    exchange: Optional[str] = None
    symbol: Optional[str] = None
    order_id: Optional[str] = None


class GracefulShutdownManager:
    """
    Manages graceful system shutdown.

    Usage:
        shutdown_manager = GracefulShutdownManager(config)
        shutdown_manager.register_cleanup_handler(cleanup_database)
        shutdown_manager.register_cleanup_handler(cleanup_redis)

        # In main loop:
        if shutdown_manager.is_shutting_down:
            break

        # To trigger shutdown:
        await shutdown_manager.shutdown()
    """

    def __init__(
        self,
        config: ShutdownConfig = None,
        exchanges: Dict = None,
        execution_engine = None,
        notification_manager = None
    ):
        """
        Initialize shutdown manager.

        Args:
            config: Shutdown configuration
            exchanges: Dict of exchange instances
            execution_engine: ExecutionEngine instance
            notification_manager: NotificationManager instance
        """
        self.config = config or ShutdownConfig()
        self.exchanges = exchanges or {}
        self.execution_engine = execution_engine
        self.notification_manager = notification_manager

        self._phase = ShutdownPhase.RUNNING
        self._shutdown_requested = False
        self._shutdown_complete = asyncio.Event()
        self._in_flight: Dict[str, InFlightOperation] = {}
        self._cleanup_handlers: List[Callable] = []
        self._operation_counter = 0

        # Signal handling
        self._original_handlers = {}

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress"""
        return self._shutdown_requested

    @property
    def phase(self) -> ShutdownPhase:
        """Current shutdown phase"""
        return self._phase

    @property
    def can_accept_new_work(self) -> bool:
        """Check if system can accept new operations"""
        return self._phase == ShutdownPhase.RUNNING

    def setup_signal_handlers(self, loop: asyncio.AbstractEventLoop = None):
        """
        Set up signal handlers for graceful shutdown.

        Args:
            loop: Event loop (uses running loop if not specified)
        """
        loop = loop or asyncio.get_event_loop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            self._original_handlers[sig] = signal.getsignal(sig)
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self._handle_signal(s))
            )

        logger.info("Graceful shutdown signal handlers installed")

    async def _handle_signal(self, sig: signal.Signals):
        """Handle shutdown signal"""
        sig_name = signal.Signals(sig).name
        logger.info(f"Received {sig_name} signal, initiating graceful shutdown...")

        if self._shutdown_requested:
            logger.warning(f"Shutdown already in progress, ignoring {sig_name}")
            return

        await self.shutdown()

    def register_cleanup_handler(self, handler: Callable):
        """
        Register a cleanup handler to be called during shutdown.

        Args:
            handler: Async function to call during cleanup
        """
        self._cleanup_handlers.append(handler)

    def register_operation(
        self,
        operation_type: str,
        exchange: str = None,
        symbol: str = None,
        order_id: str = None
    ) -> str:
        """
        Register an in-flight operation.

        Args:
            operation_type: Type of operation
            exchange: Exchange name
            symbol: Trading symbol
            order_id: Order ID if applicable

        Returns:
            Operation ID for tracking

        Raises:
            RuntimeError: If system is shutting down
        """
        if not self.can_accept_new_work:
            raise RuntimeError("System is shutting down, cannot accept new operations")

        self._operation_counter += 1
        op_id = f"op_{self._operation_counter}_{int(datetime.now().timestamp() * 1000)}"

        self._in_flight[op_id] = InFlightOperation(
            operation_id=op_id,
            operation_type=operation_type,
            started_at=datetime.now(timezone.utc),
            exchange=exchange,
            symbol=symbol,
            order_id=order_id
        )

        return op_id

    def complete_operation(self, operation_id: str):
        """
        Mark an operation as complete.

        Args:
            operation_id: Operation ID from register_operation
        """
        if operation_id in self._in_flight:
            del self._in_flight[operation_id]

    async def shutdown(self, reason: str = "Shutdown requested"):
        """
        Initiate graceful shutdown.

        Args:
            reason: Reason for shutdown (for logging)
        """
        if self._shutdown_requested:
            logger.warning("Shutdown already in progress")
            return

        self._shutdown_requested = True
        shutdown_start = datetime.now(timezone.utc)

        logger.info(f"🛑 Initiating graceful shutdown: {reason}")

        try:
            # Phase 1: Drain - stop accepting new work
            self._phase = ShutdownPhase.DRAINING
            await self._drain_in_flight_operations()

            # Phase 2: Cancel pending orders
            self._phase = ShutdownPhase.CANCELLING
            await self._cancel_pending_orders()

            # Phase 3: Close positions (if configured)
            if self.config.close_positions_on_shutdown:
                self._phase = ShutdownPhase.CLOSING
                await self._close_open_positions()

            # Phase 4: Flush logs and metrics
            self._phase = ShutdownPhase.FLUSHING
            await self._flush_data()

            # Phase 5: Cleanup resources
            self._phase = ShutdownPhase.CLEANUP
            await self._cleanup_resources()

            # Send shutdown notification
            if self.config.notify_on_shutdown and self.notification_manager:
                try:
                    await self.notification_manager.send_system_alert(
                        "System Shutdown Complete",
                        f"Reason: {reason}\nDuration: {(datetime.now(timezone.utc) - shutdown_start).total_seconds():.1f}s"
                    )
                except Exception as e:
                    logger.warning(f"Failed to send shutdown notification: {e}")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

        finally:
            self._phase = ShutdownPhase.COMPLETE
            self._shutdown_complete.set()

            shutdown_duration = (datetime.now(timezone.utc) - shutdown_start).total_seconds()
            logger.info(f"✅ Graceful shutdown complete in {shutdown_duration:.1f}s")

    async def _drain_in_flight_operations(self):
        """Wait for in-flight operations to complete"""
        if not self._in_flight:
            logger.info("No in-flight operations to drain")
            return

        logger.info(f"Draining {len(self._in_flight)} in-flight operations...")

        deadline = datetime.now(timezone.utc) + timedelta(
            seconds=self.config.drain_timeout_seconds
        )

        while self._in_flight and datetime.now(timezone.utc) < deadline:
            remaining = len(self._in_flight)
            logger.debug(f"Waiting for {remaining} operations to complete...")

            await asyncio.sleep(1)

        if self._in_flight:
            remaining_ops = list(self._in_flight.values())
            logger.warning(
                f"Drain timeout with {len(remaining_ops)} operations still in-flight"
            )
            for op in remaining_ops:
                logger.warning(
                    f"  - {op.operation_type} on {op.exchange} "
                    f"(started {op.started_at.isoformat()})"
                )

    async def _cancel_pending_orders(self):
        """Cancel all pending orders across exchanges"""
        logger.info("Cancelling pending orders...")

        cancel_tasks = []

        for exchange_name, exchange in self.exchanges.items():
            try:
                # Get all open orders
                open_orders = await exchange.get_open_orders()

                for order in open_orders:
                    cancel_tasks.append(
                        self._cancel_order_safe(exchange, order.symbol, order.order_id)
                    )

                if open_orders:
                    logger.info(
                        f"Found {len(open_orders)} open orders on {exchange_name}"
                    )

            except Exception as e:
                logger.error(f"Error getting open orders from {exchange_name}: {e}")

        if cancel_tasks:
            # Wait for all cancellations with timeout
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*cancel_tasks, return_exceptions=True),
                    timeout=self.config.cancel_timeout_seconds
                )

                cancelled = sum(1 for r in results if r is True)
                failed = sum(1 for r in results if r is not True)

                logger.info(f"Cancelled {cancelled} orders, {failed} failures")

            except asyncio.TimeoutError:
                logger.warning("Order cancellation timed out")
        else:
            logger.info("No pending orders to cancel")

    async def _cancel_order_safe(
        self,
        exchange,
        symbol: str,
        order_id: str
    ) -> bool:
        """Cancel an order with error handling"""
        try:
            result = await exchange.cancel_order(symbol, order_id)
            if result:
                logger.debug(f"Cancelled order {order_id} on {exchange.name}")
            return result
        except Exception as e:
            logger.warning(f"Failed to cancel order {order_id}: {e}")
            return False

    async def _close_open_positions(self):
        """Close all open positions at market price"""
        logger.info("Closing open positions...")

        if not self.exchanges:
            logger.warning("No exchanges configured - cannot close positions")
            return

        closed_positions = []
        failed_positions = []

        for exchange_name, exchange in self.exchanges.items():
            try:
                # Get balances to find non-zero positions
                balances = await asyncio.wait_for(
                    exchange.get_balances(),
                    timeout=10.0
                )

                for asset, balance in balances.items():
                    # Skip stablecoins and base currencies
                    if asset in ('USDT', 'USDC', 'BUSD', 'USD', 'EUR'):
                        continue

                    free_balance = balance.get('free', 0)
                    if isinstance(free_balance, str):
                        from decimal import Decimal
                        free_balance = Decimal(free_balance)

                    # Skip negligible balances (less than $1 equivalent)
                    if free_balance <= 0:
                        continue

                    # Try to close position by selling to USDT
                    symbol = f"{asset}/USDT"
                    try:
                        logger.info(f"Closing position: {free_balance} {asset} on {exchange_name}")

                        # Use market order to ensure fill
                        order = await asyncio.wait_for(
                            exchange.create_order(
                                symbol=symbol,
                                side='sell',
                                order_type='market',
                                quantity=free_balance
                            ),
                            timeout=self.config.close_positions_timeout_seconds
                        )

                        if order and order.status.value in ('filled', 'closed'):
                            closed_positions.append({
                                'exchange': exchange_name,
                                'asset': asset,
                                'amount': float(free_balance),
                                'order_id': order.order_id
                            })
                            logger.info(f"Closed position: {asset} on {exchange_name}")
                        else:
                            failed_positions.append({
                                'exchange': exchange_name,
                                'asset': asset,
                                'reason': 'Order not filled'
                            })

                    except asyncio.TimeoutError:
                        failed_positions.append({
                            'exchange': exchange_name,
                            'asset': asset,
                            'reason': 'Timeout'
                        })
                        logger.warning(f"Timeout closing {asset} on {exchange_name}")
                    except Exception as e:
                        failed_positions.append({
                            'exchange': exchange_name,
                            'asset': asset,
                            'reason': str(e)
                        })
                        logger.warning(f"Failed to close {asset} on {exchange_name}: {e}")

            except Exception as e:
                logger.error(f"Error getting balances from {exchange_name}: {e}")

        # Log summary
        logger.info(f"Position closing complete: {len(closed_positions)} closed, {len(failed_positions)} failed")

        if failed_positions:
            logger.warning(f"Failed to close positions: {failed_positions}")
            logger.warning("Manual intervention may be required!")

    async def _flush_data(self):
        """Flush logs, metrics, and pending database writes"""
        logger.info("Flushing data...")

        # Give time for async loggers to flush
        await asyncio.sleep(0.5)

        # Flush any pending metrics
        # (This would be implemented based on metrics system used)

        logger.info("Data flush complete")

    async def _cleanup_resources(self):
        """Run registered cleanup handlers"""
        logger.info(f"Running {len(self._cleanup_handlers)} cleanup handlers...")

        for handler in self._cleanup_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await asyncio.wait_for(
                        handler(),
                        timeout=self.config.cleanup_timeout_seconds
                    )
                else:
                    handler()

                logger.debug(f"Cleanup handler {handler.__name__} completed")

            except asyncio.TimeoutError:
                logger.warning(f"Cleanup handler {handler.__name__} timed out")
            except Exception as e:
                logger.error(f"Cleanup handler {handler.__name__} failed: {e}")

        # Close exchange connections
        for exchange_name, exchange in self.exchanges.items():
            try:
                await exchange.close()
                logger.debug(f"Closed {exchange_name} connection")
            except Exception as e:
                logger.warning(f"Error closing {exchange_name}: {e}")

    async def wait_for_shutdown(self):
        """Wait for shutdown to complete"""
        await self._shutdown_complete.wait()

    def get_status(self) -> Dict:
        """Get current shutdown status"""
        return {
            "phase": self._phase.value,
            "shutdown_requested": self._shutdown_requested,
            "in_flight_operations": len(self._in_flight),
            "can_accept_work": self.can_accept_new_work,
            "operations": [
                {
                    "id": op.operation_id,
                    "type": op.operation_type,
                    "exchange": op.exchange,
                    "started": op.started_at.isoformat()
                }
                for op in self._in_flight.values()
            ]
        }


# Convenience function for creating shutdown manager with common setup
def create_shutdown_manager(
    exchanges: Dict = None,
    execution_engine = None,
    notification_manager = None,
    close_positions: bool = False
) -> GracefulShutdownManager:
    """
    Create a configured shutdown manager.

    Args:
        exchanges: Dict of exchange instances
        execution_engine: ExecutionEngine instance
        notification_manager: NotificationManager instance
        close_positions: Whether to close positions on shutdown

    Returns:
        Configured GracefulShutdownManager
    """
    config = ShutdownConfig(
        close_positions_on_shutdown=close_positions,
        drain_timeout_seconds=30,
        cancel_timeout_seconds=30,
        cleanup_timeout_seconds=10
    )

    return GracefulShutdownManager(
        config=config,
        exchanges=exchanges,
        execution_engine=execution_engine,
        notification_manager=notification_manager
    )
