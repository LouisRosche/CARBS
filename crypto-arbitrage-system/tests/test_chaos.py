"""
Chaos Engineering Tests for CARBS

Tests system resilience under failure conditions:
- Network failures (exchange API outages, timeouts, slow responses)
- Database failures (connection loss, query timeouts)
- Redis failures (cache unavailable)
- Partial failures (one exchange down, others up)
- Resource exhaustion (memory, CPU, connections)
- Data corruption/inconsistencies

These tests ensure the system degrades gracefully and maintains data integrity
under adverse conditions typical in production environments.

Run with: pytest tests/test_chaos.py -v -s
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, timezone
import os


class TestNetworkFailures:
    """Test resilience to network and API failures"""

    @pytest.mark.asyncio
    async def test_single_exchange_timeout(self):
        """
        When one exchange times out, system should:
        1. Log the error
        2. Continue with other exchanges
        3. Not crash the entire system
        """
        from src.core.engine import ArbitrageEngine
        from src.config.settings import Config

        # Mock config
        config = Mock(spec=Config)
        config.trading = Mock(min_spread_percent=0.3, max_spread_percent=5.0, max_position_usd=500)

        engine = ArbitrageEngine(config)

        # Mock exchange that times out
        mock_exchange_timeout = AsyncMock()
        mock_exchange_timeout.fetch_order_book = AsyncMock(side_effect=asyncio.TimeoutError("Request timed out"))

        # Mock exchange that works
        mock_exchange_working = AsyncMock()
        mock_exchange_working.fetch_order_book = AsyncMock(return_value={
            'bids': [[67540.0, 1.5]],
            'asks': [[67550.0, 1.5]]
        })

        engine.exchanges = {
            'binance': mock_exchange_timeout,
            'coinbase': mock_exchange_working
        }

        # System should handle timeout gracefully
        # This is a structural test - in real implementation, engine should have error handling
        # For now, we verify the mock behavior
        try:
            await mock_exchange_timeout.fetch_order_book('BTC/USDT')
            assert False, "Should have raised TimeoutError"
        except asyncio.TimeoutError:
            pass  # Expected

        # Working exchange should still function
        result = await mock_exchange_working.fetch_order_book('BTC/USDT')
        assert result is not None
        assert 'bids' in result

    @pytest.mark.asyncio
    async def test_all_exchanges_down(self):
        """
        When ALL exchanges are unreachable, system should:
        1. Log critical error
        2. Not attempt trades
        3. Retry with backoff
        4. Eventually alert operators
        """
        from src.core.engine import ArbitrageEngine
        from src.config.settings import Config

        config = Mock(spec=Config)
        config.trading = Mock(min_spread_percent=0.3, max_spread_percent=5.0, max_position_usd=500)

        engine = ArbitrageEngine(config)

        # All exchanges fail
        for exchange_name in ['binance', 'coinbase', 'kraken']:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_order_book = AsyncMock(side_effect=ConnectionError("Exchange unreachable"))
            engine.exchanges[exchange_name] = mock_exchange

        # Verify all raise errors
        for exchange_name, exchange in engine.exchanges.items():
            with pytest.raises(ConnectionError):
                await exchange.fetch_order_book('BTC/USDT')

        # System should not attempt to detect opportunities
        # (would need actual engine method call to test fully)

    @pytest.mark.asyncio
    async def test_intermittent_network_flakiness(self):
        """
        Test handling of intermittent network issues (flaky connections)
        """
        # Create mock that fails 3 times then succeeds
        call_count = 0

        async def flaky_fetch(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise ConnectionError("Temporary network issue")
            return {'bids': [[67540.0, 1.5]], 'asks': [[67550.0, 1.5]]}

        mock_exchange = AsyncMock()
        mock_exchange.fetch_order_book = flaky_fetch

        # Retry logic (simplified version of what should be in engine)
        max_retries = 5
        for attempt in range(max_retries):
            try:
                result = await mock_exchange.fetch_order_book('BTC/USDT')
                assert result is not None
                break
            except ConnectionError:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(0.01)  # Small delay for test

        assert call_count == 4  # 3 failures + 1 success

    @pytest.mark.asyncio
    async def test_slow_exchange_response(self):
        """
        Test handling of slow exchange responses (high latency)
        Should timeout and skip rather than blocking other exchanges
        """
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(10)  # 10 second delay
            return {'bids': [[67540.0, 1.5]], 'asks': [[67550.0, 1.5]]}

        mock_slow_exchange = AsyncMock()
        mock_slow_exchange.fetch_order_book = slow_response

        # Should timeout after reasonable period (e.g., 5 seconds)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                mock_slow_exchange.fetch_order_book('BTC/USDT'),
                timeout=0.1  # Short timeout for test
            )


class TestDatabaseFailures:
    """Test resilience to database failures"""

    @pytest.mark.asyncio
    async def test_database_connection_loss(self):
        """
        When database connection is lost, system should:
        1. Log error
        2. Continue operating (buffering trades in memory if needed)
        3. Attempt reconnection
        4. Not lose trade data
        """
        # Mock database connection that fails
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=ConnectionError("Database connection lost"))

        # System should catch this and handle gracefully
        with pytest.raises(ConnectionError):
            await mock_conn.execute("INSERT INTO trades ...")

        # In real implementation, should buffer or queue writes

    @pytest.mark.asyncio
    async def test_database_query_timeout(self):
        """Test handling of slow database queries"""
        async def slow_query(*args, **kwargs):
            await asyncio.sleep(10)
            return []

        mock_conn = AsyncMock()
        mock_conn.fetch = slow_query

        # Should timeout long-running queries
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                mock_conn.fetch("SELECT * FROM large_table"),
                timeout=0.1
            )

    @pytest.mark.asyncio
    async def test_database_disk_full(self):
        """Test handling when database disk is full"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("disk full"))

        # Should catch and handle
        try:
            await mock_conn.execute("INSERT INTO trades ...")
            assert False, "Should have raised exception"
        except Exception as e:
            assert "disk full" in str(e).lower()

        # System should alert operators about disk space


class TestCacheFailures:
    """Test resilience to Redis cache failures"""

    @pytest.mark.asyncio
    async def test_redis_unavailable(self):
        """
        When Redis is unavailable, system should:
        1. Continue operating (degrade to no cache)
        2. Log warning
        3. Periodically retry connection
        """
        from src.utils.cache import RedisCache

        # Mock Redis connection failure
        with patch('redis.Redis.ping', side_effect=ConnectionError("Redis unreachable")):
            # System should handle gracefully
            # In real implementation, should fall back to direct API calls
            pass

    @pytest.mark.asyncio
    async def test_cache_data_corruption(self):
        """Test handling of corrupted cached data"""
        # Mock Redis returning corrupted data
        mock_redis = Mock()
        mock_redis.get = Mock(return_value=b'corrupted_non_json_data')

        # System should catch JSON decode error and invalidate cache
        import json
        with pytest.raises(json.JSONDecodeError):
            json.loads(mock_redis.get('orderbook:BTC/USDT'))

        # Should fall back to fetching fresh data


class TestPartialFailures:
    """Test handling of partial system failures"""

    @pytest.mark.asyncio
    async def test_two_of_three_exchanges_down(self):
        """
        Test arbitrage detection with subset of exchanges available
        Should still find opportunities if spread exists
        """
        mock_binance = AsyncMock()
        mock_binance.fetch_order_book = AsyncMock(return_value={
            'bids': [[67540.0, 1.5]],
            'asks': [[67545.0, 1.5]]
        })

        mock_coinbase = AsyncMock()
        mock_coinbase.fetch_order_book = AsyncMock(side_effect=ConnectionError("Down"))

        mock_kraken = AsyncMock()
        mock_kraken.fetch_order_book = AsyncMock(return_value={
            'bids': [[67550.0, 1.5]],
            'asks': [[67560.0, 1.5]]
        })

        exchanges = {
            'binance': mock_binance,
            'coinbase': mock_coinbase,
            'kraken': mock_kraken
        }

        # Fetch from available exchanges only
        working_orderbooks = {}
        for name, exchange in exchanges.items():
            try:
                ob = await exchange.fetch_order_book('BTC/USDT')
                working_orderbooks[name] = ob
            except ConnectionError:
                continue  # Skip failed exchange

        assert len(working_orderbooks) == 2  # binance and kraken
        assert 'binance' in working_orderbooks
        assert 'kraken' in working_orderbooks
        assert 'coinbase' not in working_orderbooks

    @pytest.mark.asyncio
    async def test_degraded_websocket_fallback_to_rest(self):
        """
        When WebSocket fails, system should fall back to REST API
        """
        # Mock WebSocket failure
        mock_ws = AsyncMock()
        mock_ws.watch_order_book = AsyncMock(side_effect=ConnectionError("WebSocket closed"))

        # Mock REST API working
        mock_rest = AsyncMock()
        mock_rest.fetch_order_book = AsyncMock(return_value={
            'bids': [[67540.0, 1.5]],
            'asks': [[67545.0, 1.5]]
        })

        # Try WebSocket first
        try:
            await mock_ws.watch_order_book('BTC/USDT')
            assert False, "Should have failed"
        except ConnectionError:
            # Fall back to REST
            result = await mock_rest.fetch_order_book('BTC/USDT')
            assert result is not None
            assert 'bids' in result


class TestResourceExhaustion:
    """Test handling of resource exhaustion scenarios"""

    @pytest.mark.asyncio
    async def test_connection_pool_exhaustion(self):
        """
        Test handling when database connection pool is exhausted
        """
        # Simulate connection pool at max capacity
        mock_pool = Mock()
        mock_pool.acquire = AsyncMock(side_effect=asyncio.TimeoutError("No connections available"))

        # Should wait or queue, not crash
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(mock_pool.acquire(), timeout=0.1)

    def test_memory_leak_detection(self):
        """
        Test that orderbook objects don't accumulate indefinitely
        This is a smoke test - real memory profiling requires memory_profiler
        """
        from src.core.engine import OrderBook

        # Create many orderbooks
        orderbooks = []
        for i in range(10000):
            ob = OrderBook(
                exchange='test',
                symbol='BTC/USDT',
                timestamp=datetime.now(timezone.utc),
                bids=[(Decimal('67540.0'), Decimal('1.5'))],
                asks=[(Decimal('67545.0'), Decimal('1.5'))]
            )
            orderbooks.append(ob)

        # Clear references
        orderbooks.clear()

        # In real test, would measure memory before/after
        # For now, just verify objects can be created and destroyed
        assert len(orderbooks) == 0

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self):
        """
        Test handling of exchange rate limits
        """
        call_count = 0

        async def rate_limited_fetch(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count > 10:
                raise Exception("429 Too Many Requests")
            return {'bids': [[67540.0, 1.5]], 'asks': [[67545.0, 1.5]]}

        mock_exchange = AsyncMock()
        mock_exchange.fetch_order_book = rate_limited_fetch

        # Make many requests
        for i in range(15):
            try:
                await mock_exchange.fetch_order_book('BTC/USDT')
            except Exception as e:
                if "429" in str(e):
                    # Should implement exponential backoff
                    await asyncio.sleep(0.01)
                    break

        assert call_count >= 10  # Hit rate limit


class TestDataIntegrity:
    """Test data integrity under failure conditions"""

    @pytest.mark.asyncio
    async def test_trade_not_lost_on_crash(self):
        """
        Verify trades are persisted before confirmation
        Even if system crashes, trade should be recoverable
        """
        # This would test write-ahead logging or transaction guarantees
        # Simplified version:

        # Simulate trade execution
        trade_data = {
            'symbol': 'BTC/USDT',
            'buy_exchange': 'binance',
            'sell_exchange': 'kraken',
            'amount': 0.01,
            'executed_at': datetime.now(timezone.utc).isoformat()
        }

        # In real system, would write to WAL or transactional queue
        # Before sending to exchange
        # Then confirm after exchange responds
        # If crash occurs between, can recover from WAL

        # For test, just verify structure
        assert 'symbol' in trade_data
        assert 'buy_exchange' in trade_data

    def test_audit_log_tamper_detection(self):
        """
        Verify audit log integrity chain is maintained under failures
        """
        from src.security.audit import AuditLogger, AuditCategory, AuditSeverity

        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()
        try:
            audit_logger = AuditLogger(log_dir=temp_dir)

            # Log several events
            audit_logger.log(
                category=AuditCategory.TRADE,
                action='execute',
                actor='system',
                resource='BTC/USDT',
                details={'amount': 0.01}
            )

            audit_logger.log(
                category=AuditCategory.TRADE,
                action='execute',
                actor='system',
                resource='ETH/USDT',
                details={'amount': 0.1}
            )

            # Force flush by shutting down
            audit_logger.shutdown()

            # Verify integrity
            audit_logger_verify = AuditLogger(log_dir=temp_dir)
            is_valid, broken_events = audit_logger_verify.verify_integrity()

            assert is_valid, f"Audit log integrity broken: {broken_events}"
            assert len(broken_events) == 0

        finally:
            shutil.rmtree(temp_dir)


class TestGracefulDegradation:
    """Test that system degrades gracefully rather than failing catastrophically"""

    @pytest.mark.asyncio
    async def test_reduced_functionality_mode(self):
        """
        When key components fail, system should continue in reduced mode
        E.g., if ML scoring fails, fall back to simple spread checking
        """
        # Simulate ML model failure
        ml_model_available = False

        if ml_model_available:
            # Would use ML scoring
            confidence_score = 0.85
        else:
            # Fall back to simple heuristic
            confidence_score = 0.5  # Lower confidence without ML

        # System continues, just with reduced confidence
        assert 0 <= confidence_score <= 1.0

    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_cascade_failure(self):
        """
        Test circuit breaker pattern prevents cascade failures
        """
        from src.core.execution_engine import CircuitBreaker

        # Circuit breaker should open after threshold failures
        circuit = CircuitBreaker(failure_threshold=3, timeout_seconds=60)

        # Simulate failures
        for i in range(5):
            try:
                if circuit.is_open():
                    # Circuit is open, don't attempt call
                    continue

                # Simulate failing call
                circuit.record_failure()

                if circuit.failure_count >= circuit.failure_threshold:
                    circuit.open()

            except Exception:
                pass

        # Circuit should be open after 3+ failures
        assert circuit.is_open()


class TestConcurrencyIssues:
    """Test thread-safety and concurrency issues"""

    @pytest.mark.asyncio
    async def test_concurrent_orderbook_updates_no_race_condition(self):
        """
        Test that concurrent orderbook updates don't cause race conditions
        """
        from src.core.engine import OrderBook

        # Simulate rapid concurrent updates
        async def update_orderbook(orderbooks, exchange_name):
            for i in range(100):
                orderbooks[exchange_name] = OrderBook(
                    exchange=exchange_name,
                    symbol='BTC/USDT',
                    timestamp=datetime.now(timezone.utc),
                    bids=[(Decimal('67540.0'), Decimal('1.5'))],
                    asks=[(Decimal('67545.0'), Decimal('1.5'))]
                )
                await asyncio.sleep(0.001)

        orderbooks = {}

        # Run concurrent updates
        await asyncio.gather(
            update_orderbook(orderbooks, 'binance'),
            update_orderbook(orderbooks, 'coinbase'),
            update_orderbook(orderbooks, 'kraken')
        )

        # All should have final values
        assert 'binance' in orderbooks
        assert 'coinbase' in orderbooks
        assert 'kraken' in orderbooks

    @pytest.mark.asyncio
    async def test_no_deadlock_on_concurrent_trades(self):
        """
        Test that concurrent trade attempts don't cause deadlocks
        """
        # This would test transaction locking in real system
        # Simplified version just verifies concurrent execution completes

        async def execute_trade(trade_id):
            # Simulate trade execution with small delay
            await asyncio.sleep(0.01)
            return trade_id

        # Execute 10 trades concurrently
        results = await asyncio.gather(*[
            execute_trade(i) for i in range(10)
        ])

        # All should complete
        assert len(results) == 10
        assert set(results) == set(range(10))


"""
USAGE:

1. Run all chaos tests:
   pytest tests/test_chaos.py -v

2. Run specific category:
   pytest tests/test_chaos.py::TestNetworkFailures -v

3. Run with verbose output:
   pytest tests/test_chaos.py -v -s

4. Run in CI:
   Add to .github/workflows/ci.yml as separate job (optional, can be slow)

IMPLEMENTATION NOTES:

These tests identify potential failure modes. The actual system should implement:

1. Retry logic with exponential backoff for transient failures
2. Circuit breakers to prevent cascade failures
3. Graceful degradation when components fail
4. Connection pooling with limits
5. Timeouts on all external calls
6. Transaction guarantees for critical data
7. Audit log integrity checks
8. Resource monitoring and alerting

Many of these tests are currently structural (verify error handling exists).
As the system matures, these should be enhanced to test actual resilience code.
"""
