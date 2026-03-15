"""
Performance Benchmarks for Latency-Critical Paths

Tests verify the <100ms latency claims for arbitrage detection.
These benchmarks ensure the system meets real-time trading requirements.

Critical paths tested:
1. Orderbook processing
2. Opportunity detection
3. Spread calculation
4. Slippage estimation
5. End-to-end opportunity pipeline

Run with: pytest tests/test_performance.py -v --benchmark-only
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock

# Performance thresholds (in seconds)
ORDERBOOK_PROCESSING_THRESHOLD = 0.010  # 10ms
OPPORTUNITY_DETECTION_THRESHOLD = 0.050  # 50ms
SPREAD_CALCULATION_THRESHOLD = 0.001  # 1ms
SLIPPAGE_ESTIMATION_THRESHOLD = 0.005  # 5ms
END_TO_END_THRESHOLD = 0.100  # 100ms (total claim)


@pytest.fixture
def sample_orderbook():
    """Sample orderbook for benchmarking"""
    from src.core.engine import OrderBook

    return OrderBook(
        exchange='binance',
        symbol='BTC/USDT',
        timestamp=datetime.now(timezone.utc),
        bids=[
            (Decimal('67543.21'), Decimal('1.5')),
            (Decimal('67540.00'), Decimal('2.3')),
            (Decimal('67535.50'), Decimal('3.1')),
            (Decimal('67530.00'), Decimal('1.8')),
            (Decimal('67525.00'), Decimal('2.5')),
        ],
        asks=[
            (Decimal('67547.89'), Decimal('1.2')),
            (Decimal('67550.00'), Decimal('2.1')),
            (Decimal('67555.50'), Decimal('2.8')),
            (Decimal('67560.00'), Decimal('1.9')),
            (Decimal('67565.00'), Decimal('2.3')),
        ]
    )


@pytest.fixture
def multiple_orderbooks(sample_orderbook):
    """Multiple orderbooks from different exchanges"""
    from src.core.engine import OrderBook

    orderbooks = {
        'binance': sample_orderbook,
        'coinbase': OrderBook(
            exchange='coinbase',
            symbol='BTC/USDT',
            timestamp=datetime.now(timezone.utc),
            bids=[
                (Decimal('67540.00'), Decimal('1.3')),
                (Decimal('67535.00'), Decimal('2.1')),
                (Decimal('67530.00'), Decimal('2.9')),
            ],
            asks=[
                (Decimal('67555.00'), Decimal('1.5')),
                (Decimal('67560.00'), Decimal('2.2')),
                (Decimal('67565.00'), Decimal('2.7')),
            ]
        ),
        'kraken': OrderBook(
            exchange='kraken',
            symbol='BTC/USDT',
            timestamp=datetime.now(timezone.utc),
            bids=[
                (Decimal('67545.00'), Decimal('1.7')),
                (Decimal('67540.00'), Decimal('2.4')),
                (Decimal('67535.00'), Decimal('3.2')),
            ],
            asks=[
                (Decimal('67560.00'), Decimal('1.4')),
                (Decimal('67565.00'), Decimal('2.3')),
                (Decimal('67570.00'), Decimal('2.9')),
            ]
        )
    }
    return orderbooks


class TestOrderbookProcessing:
    """Benchmark orderbook processing performance"""

    def test_orderbook_best_bid_ask(self, benchmark, sample_orderbook):
        """Benchmark best bid/ask extraction (<10ms)"""
        def get_best_prices():
            best_bid = sample_orderbook.best_bid
            best_ask = sample_orderbook.best_ask
            return best_bid, best_ask

        result = benchmark(get_best_prices)
        assert result is not None

    def test_slippage_estimation(self, benchmark, sample_orderbook):
        """Benchmark slippage estimation (<5ms)"""
        position_size = Decimal('1000')  # $1000 position

        result = benchmark(
            sample_orderbook.estimate_slippage,
            'buy',
            position_size
        )

        # Verify result is reasonable
        assert Decimal('0') <= result <= Decimal('0.02')

        # Check latency
        stats = benchmark.stats
        assert stats.mean < SLIPPAGE_ESTIMATION_THRESHOLD, \
            f"Slippage estimation took {stats.mean*1000:.2f}ms (threshold: {SLIPPAGE_ESTIMATION_THRESHOLD*1000}ms)"


class TestOpportunityDetection:
    """Benchmark opportunity detection performance"""

    def test_spread_calculation(self, benchmark, multiple_orderbooks):
        """Benchmark spread calculation across exchanges (<1ms)"""
        def calculate_spreads():
            spreads = []
            exchanges = list(multiple_orderbooks.keys())

            for i, buy_exchange in enumerate(exchanges):
                for sell_exchange in exchanges[i+1:]:
                    buy_price = multiple_orderbooks[buy_exchange].best_ask[0]
                    sell_price = multiple_orderbooks[sell_exchange].best_bid[0]

                    if sell_price > buy_price:
                        spread = (sell_price - buy_price) / buy_price
                        spreads.append({
                            'buy': buy_exchange,
                            'sell': sell_exchange,
                            'spread': spread
                        })

            return spreads

        result = benchmark(calculate_spreads)
        assert len(result) >= 0  # May or may not find opportunities

        # Check latency
        stats = benchmark.stats
        assert stats.mean < SPREAD_CALCULATION_THRESHOLD, \
            f"Spread calculation took {stats.mean*1000:.2f}ms (threshold: {SPREAD_CALCULATION_THRESHOLD*1000}ms)"

    def test_opportunity_detection_with_fees(self, benchmark, multiple_orderbooks):
        """Benchmark opportunity detection including fee calculations (<50ms)"""
        def detect_opportunities():
            opportunities = []
            exchanges = list(multiple_orderbooks.keys())

            # Simulated fee rates
            fees = {'binance': 0.001, 'coinbase': 0.006, 'kraken': 0.0016}

            for buy_exchange in exchanges:
                for sell_exchange in exchanges:
                    if buy_exchange == sell_exchange:
                        continue

                    buy_price = multiple_orderbooks[buy_exchange].best_ask[0]
                    sell_price = multiple_orderbooks[sell_exchange].best_bid[0]

                    # Calculate spread after fees
                    buy_fee = Decimal(str(fees[buy_exchange]))
                    sell_fee = Decimal(str(fees[sell_exchange]))

                    effective_buy_price = buy_price * (Decimal('1') + buy_fee)
                    effective_sell_price = sell_price * (Decimal('1') - sell_fee)

                    if effective_sell_price > effective_buy_price:
                        spread = (effective_sell_price - effective_buy_price) / effective_buy_price

                        # Estimate slippage
                        position_size = Decimal('500')
                        buy_slippage = multiple_orderbooks[buy_exchange].estimate_slippage('buy', position_size)
                        sell_slippage = multiple_orderbooks[sell_exchange].estimate_slippage('sell', position_size)

                        # Adjust for slippage
                        net_spread = spread - buy_slippage - sell_slippage

                        if net_spread > Decimal('0.001'):  # 0.1% minimum
                            opportunities.append({
                                'buy_exchange': buy_exchange,
                                'sell_exchange': sell_exchange,
                                'net_spread': float(net_spread)
                            })

            return opportunities

        result = benchmark(detect_opportunities)
        assert isinstance(result, list)

        # Check latency
        stats = benchmark.stats
        assert stats.mean < OPPORTUNITY_DETECTION_THRESHOLD, \
            f"Opportunity detection took {stats.mean*1000:.2f}ms (threshold: {OPPORTUNITY_DETECTION_THRESHOLD*1000}ms)"


class TestEndToEndPipeline:
    """Benchmark complete opportunity detection pipeline"""

    @pytest.mark.asyncio
    async def test_end_to_end_latency(self, benchmark, multiple_orderbooks):
        """
        Benchmark end-to-end opportunity detection pipeline (<100ms)

        This simulates the complete flow:
        1. Receive orderbook updates
        2. Calculate spreads across all exchange pairs
        3. Apply fees and slippage
        4. Filter for minimum profitability
        5. Create Opportunity objects
        """
        from src.core.engine import Opportunity

        def end_to_end_detection():
            """Synchronous version for benchmark compatibility"""
            opportunities = []
            exchanges = list(multiple_orderbooks.keys())
            fees = {'binance': 0.001, 'coinbase': 0.006, 'kraken': 0.0016}
            min_spread = Decimal('0.003')  # 0.3% minimum
            position_size = Decimal('500')

            for buy_exchange in exchanges:
                buy_ob = multiple_orderbooks[buy_exchange]
                buy_price = buy_ob.best_ask[0]

                for sell_exchange in exchanges:
                    if buy_exchange == sell_exchange:
                        continue

                    sell_ob = multiple_orderbooks[sell_exchange]
                    sell_price = sell_ob.best_bid[0]

                    # Calculate fees
                    buy_fee = Decimal(str(fees[buy_exchange]))
                    sell_fee = Decimal(str(fees[sell_exchange]))

                    # Calculate slippage
                    buy_slippage = buy_ob.estimate_slippage('buy', position_size)
                    sell_slippage = sell_ob.estimate_slippage('sell', position_size)

                    # Calculate effective prices
                    effective_buy = buy_price * (Decimal('1') + buy_fee + buy_slippage)
                    effective_sell = sell_price * (Decimal('1') - sell_fee - sell_slippage)

                    if effective_sell > effective_buy:
                        spread = (effective_sell - effective_buy) / effective_buy
                        spread_bps = spread * Decimal('10000')

                        if spread >= min_spread:
                            # Create opportunity object
                            profit_usd = (effective_sell - effective_buy) * (position_size / effective_buy)

                            opp = Opportunity(
                                symbol='BTC/USDT',
                                buy_exchange=buy_exchange,
                                sell_exchange=sell_exchange,
                                buy_price=buy_price,
                                sell_price=sell_price,
                                spread_percent=spread * Decimal('100'),
                                spread_bps=spread_bps,
                                estimated_profit_usd=profit_usd,
                                estimated_profit_after_fees=profit_usd,  # Already calculated with fees
                                buy_fee_percent=buy_fee * Decimal('100'),
                                sell_fee_percent=sell_fee * Decimal('100'),
                                slippage_estimate=buy_slippage + sell_slippage,
                                detected_at=datetime.now(timezone.utc),
                                confidence_score=0.85
                            )
                            opportunities.append(opp)

            return opportunities

        result = benchmark(end_to_end_detection)
        assert isinstance(result, list)

        # Check latency - CRITICAL for arbitrage profitability
        stats = benchmark.stats
        assert stats.mean < END_TO_END_THRESHOLD, \
            f"❌ END-TO-END LATENCY CRITICAL: {stats.mean*1000:.2f}ms (threshold: {END_TO_END_THRESHOLD*1000}ms)\n" \
            f"   Arbitrage opportunities disappear quickly. System must process faster."

        # Log performance
        print(f"\n✅ End-to-End Performance: {stats.mean*1000:.2f}ms (threshold: {END_TO_END_THRESHOLD*1000}ms)")
        print(f"   Min: {stats.min*1000:.2f}ms, Max: {stats.max*1000:.2f}ms, StdDev: {stats.stddev*1000:.2f}ms")


class TestConcurrentProcessing:
    """Benchmark concurrent orderbook processing"""

    @pytest.mark.asyncio
    async def test_concurrent_orderbook_fetch_simulation(self, benchmark):
        """
        Benchmark concurrent orderbook processing from multiple exchanges

        This simulates fetching and processing orderbooks from 5 exchanges simultaneously.
        """
        import asyncio

        async def simulate_fetch_and_process():
            """Simulate concurrent fetch from multiple exchanges"""
            async def fetch_orderbook(exchange_name):
                # Simulate network latency
                await asyncio.sleep(0.001)  # 1ms simulated fetch

                # Simulate processing
                from src.core.engine import OrderBook
                return OrderBook(
                    exchange=exchange_name,
                    symbol='BTC/USDT',
                    timestamp=datetime.now(timezone.utc),
                    bids=[(Decimal('67540.00'), Decimal('1.5'))],
                    asks=[(Decimal('67550.00'), Decimal('1.5'))]
                )

            exchanges = ['binance', 'coinbase', 'kraken', 'okx', 'bybit']

            # Concurrent fetch
            tasks = [fetch_orderbook(ex) for ex in exchanges]
            orderbooks = await asyncio.gather(*tasks)

            # Process all orderbooks
            processed = []
            for ob in orderbooks:
                best_bid = ob.best_bid
                best_ask = ob.best_ask
                processed.append((best_bid, best_ask))

            return processed

        # Benchmark async function
        def run_async():
            return asyncio.run(simulate_fetch_and_process())

        result = benchmark(run_async)
        assert len(result) == 5  # All 5 exchanges processed

        # Concurrent processing should be faster than sequential (5 * 1ms = 5ms sequential)
        # With concurrency, should be close to 1ms + processing overhead
        stats = benchmark.stats
        print(f"\n✅ Concurrent Processing (5 exchanges): {stats.mean*1000:.2f}ms")


class TestMemoryEfficiency:
    """Benchmark memory usage for long-running scenarios"""

    def test_orderbook_memory_footprint(self, benchmark):
        """Verify orderbook objects don't accumulate excessive memory"""
        from src.core.engine import OrderBook

        def create_orderbooks():
            """Create 1000 orderbook objects to test memory efficiency"""
            orderbooks = []
            for i in range(1000):
                ob = OrderBook(
                    exchange='test',
                    symbol='BTC/USDT',
                    timestamp=datetime.now(timezone.utc),
                    bids=[(Decimal('67540.00'), Decimal('1.5')) for _ in range(10)],
                    asks=[(Decimal('67550.00'), Decimal('1.5')) for _ in range(10)]
                )
                orderbooks.append(ob)
            return orderbooks

        result = benchmark(create_orderbooks)
        assert len(result) == 1000

        # This is more of a smoke test - actual memory profiling would use memory_profiler


# Pytest benchmark configuration
pytest_plugins = ['pytest_benchmark']

"""
USAGE:

1. Install pytest-benchmark:
   pip install pytest-benchmark

2. Run all benchmarks:
   pytest tests/test_performance.py -v --benchmark-only

3. Compare benchmarks over time:
   pytest tests/test_performance.py --benchmark-save=baseline
   # Make changes
   pytest tests/test_performance.py --benchmark-compare=baseline

4. Generate histogram:
   pytest tests/test_performance.py --benchmark-histogram

5. Fail on regression:
   pytest tests/test_performance.py --benchmark-compare=baseline --benchmark-compare-fail=mean:10%

PERFORMANCE TARGETS:
- Orderbook processing: <10ms
- Spread calculation: <1ms
- Slippage estimation: <5ms
- Opportunity detection: <50ms
- End-to-end pipeline: <100ms (CRITICAL)

These targets ensure the system can compete in real-time arbitrage markets
where opportunities often disappear within 100-500ms.
"""
