"""
Tests for advanced features:
- ML-based opportunity scoring
- Almgren-Chriss slippage estimation
- Circuit breakers
- Risk management (Kelly, VaR, Sharpe)
- Cointegration testing
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from collections import deque

from src.core.advanced_engine import (
    AdvancedArbitrageEngine,
    EnhancedOrderBook,
    OpportunityScore,
    AlmgrenChrissSlippage,
    PriceHistoryTracker
)
from src.core.execution_engine import (
    ExecutionEngine,
    CircuitBreaker,
    CircuitState,
    RateLimiter,
    OrderState,
    OrderStatus
)
from src.core.risk_manager import (
    RiskManager,
    KellyCriterion,
    ValueAtRisk,
    PerformanceMetrics,
    TradeRecord
)


class MockConfig:
    """Mock configuration for testing"""
    class Trading:
        mode = 'paper'
        min_spread_percent = 0.3
        max_spread_percent = 10.0
        max_position_usd = 500
        max_daily_loss_usd = 100

    class Exchanges:
        binance = {'enabled': True, 'taker_fee': 0.001}
        coinbase = {'enabled': True, 'taker_fee': 0.006}

    trading = Trading()
    exchanges = {
        'binance': {'enabled': True, 'taker_fee': 0.001},
        'coinbase': {'enabled': True, 'taker_fee': 0.006}
    }


# ============================================================================
# Enhanced OrderBook Tests
# ============================================================================

def test_enhanced_orderbook_mid_price():
    """Test mid price calculation"""
    ob = EnhancedOrderBook(
        exchange='binance',
        symbol='BTC/USDT',
        timestamp=datetime.now(timezone.utc),
        bids=[(Decimal('50000'), Decimal('1.0'))],
        asks=[(Decimal('50100'), Decimal('1.0'))]
    )

    assert ob.mid_price == Decimal('50050')
    assert ob.spread_bps == pytest.approx(float(Decimal('19.98')), rel=0.01)


def test_enhanced_orderbook_vwap():
    """Test VWAP calculation"""
    ob = EnhancedOrderBook(
        exchange='binance',
        symbol='BTC/USDT',
        timestamp=datetime.now(timezone.utc),
        bids=[
            (Decimal('50000'), Decimal('1.0')),
            (Decimal('49900'), Decimal('2.0')),
            (Decimal('49800'), Decimal('1.0'))
        ],
        asks=[
            (Decimal('50100'), Decimal('1.0')),
            (Decimal('50200'), Decimal('2.0')),
            (Decimal('50300'), Decimal('1.0'))
        ]
    )

    # Test bid side VWAP
    vwap_bid = ob.calculate_vwap(depth=3, side='bid')
    expected = (50000 * 1 + 49900 * 2 + 49800 * 1) / 4
    assert abs(float(vwap_bid) - expected) < 1

    # Test ask side VWAP
    vwap_ask = ob.calculate_vwap(depth=3, side='ask')
    expected = (50100 * 1 + 50200 * 2 + 50300 * 1) / 4
    assert abs(float(vwap_ask) - expected) < 1


def test_liquidity_depth():
    """Test liquidity depth calculation"""
    ob = EnhancedOrderBook(
        exchange='binance',
        symbol='BTC/USDT',
        timestamp=datetime.now(timezone.utc),
        bids=[
            (Decimal('50000'), Decimal('1.0')),
            (Decimal('49900'), Decimal('1.0')),
            (Decimal('49800'), Decimal('1.0'))
        ],
        asks=[
            (Decimal('50100'), Decimal('1.0')),
            (Decimal('50200'), Decimal('1.0')),
            (Decimal('50300'), Decimal('1.0'))
        ]
    )

    depth = ob.get_liquidity_depth(Decimal('100000'))  # $100k order

    assert depth['bid_levels'] > 0
    assert depth['ask_levels'] > 0
    assert depth['bid_avg_price'] > 0
    assert depth['ask_avg_price'] > 0


# ============================================================================
# Almgren-Chriss Slippage Tests
# ============================================================================

def test_almgren_chriss_slippage():
    """Test Almgren-Chriss slippage estimation"""
    model = AlmgrenChrissSlippage()

    ob = EnhancedOrderBook(
        exchange='binance',
        symbol='BTC/USDT',
        timestamp=datetime.now(timezone.utc),
        bids=[(Decimal('50000'), Decimal('2.0'))],
        asks=[(Decimal('50100'), Decimal('2.0'))]
    )

    slippage = model.estimate_slippage(
        order_size_usd=Decimal('10000'),
        orderbook=ob
    )

    assert slippage >= 0
    assert slippage <= Decimal('0.05')  # Should be capped at 5%


def test_slippage_increases_with_size():
    """Test that slippage increases with order size"""
    model = AlmgrenChrissSlippage()

    ob = EnhancedOrderBook(
        exchange='binance',
        symbol='BTC/USDT',
        timestamp=datetime.now(timezone.utc),
        bids=[(Decimal('50000'), Decimal('1.0'))],
        asks=[(Decimal('50100'), Decimal('1.0'))]
    )

    slippage_small = model.estimate_slippage(Decimal('1000'), ob)
    slippage_large = model.estimate_slippage(Decimal('100000'), ob)

    assert slippage_large > slippage_small


# ============================================================================
# ML Opportunity Scoring Tests
# ============================================================================

def test_opportunity_score_composite():
    """Test composite score calculation"""
    score = OpportunityScore(
        spread_score=0.8,
        liquidity_score=0.9,
        volatility_score=0.7,
        timing_score=0.8,
        exchange_quality_score=0.9,
        cointegration_score=0.6
    )

    composite = score.composite_score
    assert 0 <= composite <= 1
    # With these high scores, should be > 0.7
    assert composite > 0.7


def test_opportunity_score_confidence():
    """Test confidence calculation based on score variance"""
    # Uniform scores = high confidence
    score_uniform = OpportunityScore(
        spread_score=0.8,
        liquidity_score=0.8,
        volatility_score=0.8,
        timing_score=0.8,
        exchange_quality_score=0.8,
        cointegration_score=0.8
    )

    # Varied scores = lower confidence
    score_varied = OpportunityScore(
        spread_score=1.0,
        liquidity_score=0.2,
        volatility_score=0.9,
        timing_score=0.3,
        exchange_quality_score=1.0,
        cointegration_score=0.1
    )

    assert score_uniform.confidence > score_varied.confidence


def test_advanced_engine_scoring():
    """Test advanced engine opportunity scoring"""
    config = MockConfig()
    engine = AdvancedArbitrageEngine(config)

    buy_ob = EnhancedOrderBook(
        exchange='binance',
        symbol='BTC/USDT',
        timestamp=datetime.now(timezone.utc),
        bids=[(Decimal('50000'), Decimal('2.0'))],
        asks=[(Decimal('50100'), Decimal('2.0'))]
    )

    sell_ob = EnhancedOrderBook(
        exchange='coinbase',
        symbol='BTC/USDT',
        timestamp=datetime.now(timezone.utc),
        bids=[(Decimal('50500'), Decimal('2.0'))],
        asks=[(Decimal('50600'), Decimal('2.0'))]
    )

    score = engine.score_opportunity(
        buy_orderbook=buy_ob,
        sell_orderbook=sell_ob,
        gross_spread=Decimal('0.008'),  # 0.8%
        net_spread=Decimal('0.005'),  # 0.5%
        position_size_usd=Decimal('1000'),
        min_spread=Decimal('0.003')  # 0.3%
    )

    assert isinstance(score, OpportunityScore)
    assert 0 <= score.composite_score <= 1
    assert 0 <= score.confidence <= 1


# ============================================================================
# Cointegration Tests
# ============================================================================

def test_price_history_tracker():
    """Test price history tracking"""
    tracker = PriceHistoryTracker(max_history=100)

    # Add some prices
    for i in range(50):
        price = Decimal(50000 + i * 10)
        tracker.add_price('binance', 'BTC/USDT', price, datetime.now(timezone.utc))

    prices = tracker.get_prices('binance', 'BTC/USDT')
    assert len(prices) == 50


def test_cointegration_detection():
    """Test cointegration detection"""
    tracker = PriceHistoryTracker()

    # Add cointegrated series (same with small noise)
    for i in range(50):
        base_price = 50000 + i * 10
        tracker.add_price(
            'binance', 'BTC/USDT',
            Decimal(str(base_price)), datetime.now(timezone.utc)
        )
        tracker.add_price(
            'coinbase', 'BTC/USDT',
            Decimal(str(base_price + 50)), datetime.now(timezone.utc)  # Constant spread
        )

    is_coint, p_value = tracker.test_cointegration('binance', 'coinbase', 'BTC/USDT')

    # Cointegrated series should have low p-value
    assert p_value < 0.7


# ============================================================================
# Circuit Breaker Tests
# ============================================================================

@pytest.mark.asyncio
async def test_circuit_breaker_opens_on_failures():
    """Test that circuit breaker opens after threshold failures"""
    breaker = CircuitBreaker(name='test', failure_threshold=3, timeout_seconds=1)

    async def failing_function():
        raise Exception("Test failure")

    # Try multiple times
    for _ in range(3):
        try:
            await breaker.call(failing_function)()
        except:
            pass

    assert breaker.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_half_open():
    """Test circuit breaker transitions to half-open after timeout"""
    breaker = CircuitBreaker(name='test', failure_threshold=1, timeout_seconds=0.1)

    async def failing_function():
        raise Exception("Test failure")

    # Trigger open
    try:
        await breaker.call(failing_function)()
    except:
        pass

    assert breaker.state == CircuitState.OPEN

    # Wait for timeout
    import asyncio
    await asyncio.sleep(0.2)

    # Should attempt reset
    assert breaker._should_attempt_reset()


# ============================================================================
# Rate Limiter Tests
# ============================================================================

@pytest.mark.asyncio
async def test_rate_limiter_allows_within_limit():
    """Test rate limiter allows requests within limit"""
    limiter = RateLimiter(max_requests=10, time_window_seconds=1)

    # Should allow first few requests
    for _ in range(5):
        assert await limiter.acquire()


@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_limit():
    """Test rate limiter blocks requests over limit"""
    limiter = RateLimiter(max_requests=2, time_window_seconds=1)

    # Use up tokens
    assert await limiter.acquire()
    assert await limiter.acquire()

    # Should block
    assert not await limiter.acquire()


# ============================================================================
# Kelly Criterion Tests
# ============================================================================

def test_kelly_criterion_position_sizing():
    """Test Kelly Criterion position sizing"""
    capital = Decimal('10000')
    win_prob = 0.6
    avg_win = Decimal('100')
    avg_loss = Decimal('50')

    size = KellyCriterion.calculate_position_size(
        capital=capital,
        win_probability=win_prob,
        avg_win=avg_win,
        avg_loss=avg_loss,
        safety_factor=0.25
    )

    assert size > 0
    assert size <= capital * Decimal('0.10')  # Should be capped


def test_kelly_criterion_no_bet_on_negative():
    """Test Kelly doesn't bet when edge is negative"""
    capital = Decimal('10000')
    win_prob = 0.4  # Losing edge
    avg_win = Decimal('100')
    avg_loss = Decimal('200')

    size = KellyCriterion.calculate_position_size(
        capital=capital,
        win_probability=win_prob,
        avg_win=avg_win,
        avg_loss=avg_loss
    )

    assert size == 0


# ============================================================================
# VaR Tests
# ============================================================================

def test_value_at_risk():
    """Test VaR calculation"""
    # Generate some returns
    returns = [-0.02, -0.01, 0.00, 0.01, 0.02, 0.03, -0.03, 0.01, 0.02, -0.01]

    var_95 = ValueAtRisk.calculate_var(returns, confidence=0.95)

    assert var_95 >= 0
    assert var_95 < 0.1  # Should be reasonable


def test_expected_shortfall():
    """Test Expected Shortfall calculation"""
    returns = [-0.05, -0.04, -0.02, -0.01, 0.00, 0.01, 0.02, 0.03, 0.04, 0.05]

    es = ValueAtRisk.calculate_expected_shortfall(returns, confidence=0.95)

    assert es >= 0


# ============================================================================
# Performance Metrics Tests
# ============================================================================

def test_sharpe_ratio():
    """Test Sharpe ratio calculation"""
    # Good returns
    good_returns = [0.02, 0.03, 0.01, 0.02, 0.015, 0.025, 0.02, 0.01, 0.03, 0.02]
    sharpe = PerformanceMetrics.calculate_sharpe_ratio(good_returns)

    assert sharpe > 0


def test_sortino_ratio():
    """Test Sortino ratio calculation"""
    # Mixed returns
    returns = [0.02, -0.01, 0.03, 0.01, -0.02, 0.025, 0.01, 0.02, -0.01, 0.03]
    sortino = PerformanceMetrics.calculate_sortino_ratio(returns)

    assert sortino != 0


def test_max_drawdown():
    """Test maximum drawdown calculation"""
    # Equity curve with a drawdown
    equity = [100, 105, 110, 115, 110, 105, 100, 105, 110, 115]

    max_dd, max_dd_pct = PerformanceMetrics.calculate_max_drawdown(equity)

    assert max_dd < 0  # Should be negative
    assert max_dd_pct < 0  # Should be negative percentage


# ============================================================================
# Risk Manager Integration Tests
# ============================================================================

def test_risk_manager_trade_recording():
    """Test trade recording and tracking"""
    config = MockConfig()
    rm = RiskManager(config)

    trade = TradeRecord(
        timestamp=datetime.now(timezone.utc),
        symbol='BTC/USDT',
        buy_exchange='binance',
        sell_exchange='coinbase',
        position_size=Decimal('1000'),
        gross_profit=Decimal('50'),
        net_profit=Decimal('45'),
        fees=Decimal('5'),
        execution_time_ms=100,
        success=True
    )

    rm.record_trade(trade)

    assert len(rm.trade_history) == 1
    assert len(rm.equity_curve) == 1


def test_risk_manager_position_risk():
    """Test position risk calculation"""
    config = MockConfig()
    rm = RiskManager(config)

    # Add some history
    for i in range(20):
        profit = Decimal('10') if i % 2 == 0 else Decimal('-5')
        trade = TradeRecord(
            timestamp=datetime.now(timezone.utc),
            symbol='BTC/USDT',
            buy_exchange='binance',
            sell_exchange='coinbase',
            position_size=Decimal('1000'),
            gross_profit=profit,
            net_profit=profit,
            fees=Decimal('0'),
            execution_time_ms=100,
            success=profit > 0
        )
        rm.record_trade(trade)

    risk = rm.calculate_position_risk(
        symbol='BTC/USDT',
        expected_spread=Decimal('0.005'),
        expected_fees=Decimal('0.001'),
        volatility=0.5
    )

    assert risk.recommended_size > 0
    assert 0 <= risk.risk_score <= 1
    assert 0 <= risk.win_probability <= 1


def test_risk_manager_risk_limits():
    """Test risk limit checking"""
    config = MockConfig()
    rm = RiskManager(config)

    # Should be allowed initially
    allowed, reason = rm.check_risk_limits()
    assert allowed

    # Simulate large loss
    rm.daily_pnl[datetime.now(timezone.utc).date().isoformat()] = Decimal('-150')

    allowed, reason = rm.check_risk_limits()
    assert not allowed
    assert 'Daily loss limit' in reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
