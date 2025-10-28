# Advanced Features Guide

## Overview

The advanced arbitrage system now includes **fully implemented** professional-grade features:

1. **ML-Based 6-Factor Opportunity Scoring**
2. **Almgren-Chriss Slippage Estimation**
3. **Circuit Breaker Execution Pattern**
4. **Kelly Criterion Position Sizing**
5. **VaR & Expected Shortfall Risk Metrics**
6. **Sharpe & Sortino Ratio Tracking**
7. **Statistical Arbitrage with Cointegration**

## Running the Advanced System

### Standard Mode (Basic Engine)
```bash
python src/main.py
```

### Advanced Mode (Full Features)
```bash
python src/advanced_main.py
```

## What You'll See

When running `advanced_main.py`, you'll get detailed output like:

```
================================================================================
✨ HIGH-QUALITY OPPORTUNITY DETECTED
================================================================================
Symbol: BTC/USDT
Route: Buy binance @ $67543.21 -> Sell kraken @ $67847.89
Spread: 0.451%
================================================================================
ML SCORE BREAKDOWN:
  Composite Score:      0.742 (Confidence: 0.863)
  - Spread Score:       0.856 (35% weight)
  - Liquidity Score:    0.923 (25% weight)
  - Volatility Score:   0.671 (15% weight)
  - Timing Score:       0.900 (10% weight)
  - Exchange Quality:   0.925 (10% weight)
  - Cointegration:      0.487 (5% weight)
================================================================================
RISK ANALYSIS:
  Recommended Size:     $347.82
  Kelly Optimal:        $521.45
  Win Probability:      62.5%
  Expected Return:      $1.57
  Risk Score:           0.421
  Position Sharpe:      1.85
================================================================================
🎯 Executing trade with $347.82...
✅ TRADE EXECUTED SUCCESSFULLY
================================================================================
Net Profit:           $1.43
Execution Time:       87ms
================================================================================
PORTFOLIO STATS:
  Total Trades:       15
  Win Rate:           60.0%
  Sharpe Ratio:       2.14
  Sortino Ratio:      3.21
  VaR (95%):          $12.34
  Max Drawdown:       2.3%
  Profit Factor:      1.87
================================================================================
```

## Key Differences vs Basic System

| Feature | Basic System | Advanced System |
|---------|-------------|-----------------|
| Opportunity Detection | Simple spread check | 6-factor ML scoring |
| Slippage Estimation | Fixed 5 bps | Almgren-Chriss dynamic model |
| Position Sizing | Fixed amount | Kelly Criterion optimized |
| Risk Management | Hard limits only | VaR, Sharpe, drawdown tracking |
| Execution | Direct orders | Circuit breakers + retries |
| Statistical Edge | None | Cointegration testing |

## Architecture

```
Advanced Main (advanced_main.py)
    │
    ├─► Advanced Engine (advanced_engine.py)
    │   ├── EnhancedOrderBook with VWAP
    │   ├── 6-Factor ML Scoring
    │   ├── Almgren-Chriss Slippage
    │   └── Cointegration Testing
    │
    ├─► Execution Engine (execution_engine.py)
    │   ├── Circuit Breakers
    │   ├── Rate Limiters (Token Bucket)
    │   ├── Retry Logic (Exponential Backoff)
    │   └── Order State Management
    │
    └─► Risk Manager (risk_manager.py)
        ├── Kelly Criterion Position Sizing
        ├── VaR (95% & 99%)
        ├── Expected Shortfall
        ├── Sharpe & Sortino Ratios
        └── Drawdown Tracking
```

## Configuration

All settings are in `config/config.yaml`. The advanced system uses the same configuration but makes better decisions:

```yaml
trading:
  mode: paper  # Start with paper trading
  min_spread_percent: 0.3
  max_position_usd: 500  # Used as constraint, actual size from Kelly
```

The advanced system will:
- Calculate optimal position size using Kelly Criterion
- Apply safety factors and constraints
- Monitor risk limits continuously
- Adjust positions based on performance

## Testing

Run the comprehensive test suite:

```bash
pytest tests/test_advanced_features.py -v
```

Tests cover:
- ML opportunity scoring
- Almgren-Chriss slippage estimation
- Circuit breaker state transitions
- Rate limiting
- Kelly Criterion calculations
- VaR and Expected Shortfall
- Sharpe and Sortino ratios
- Cointegration detection

## Performance Metrics

The system tracks and displays:

**Per-Trade Metrics:**
- Composite ML score (0-1)
- Score confidence level
- Individual factor scores
- Recommended position size
- Expected return and risk

**Portfolio Metrics:**
- Win rate
- Sharpe ratio (risk-adjusted returns)
- Sortino ratio (downside deviation)
- VaR at 95% and 99% confidence
- Maximum drawdown
- Profit factor (gross profit / gross loss)
- Average win vs average loss

## Research Implementation

All algorithms are based on peer-reviewed research:

1. **Kelly, J.L. (1956)** - Optimal bet sizing
   - Implementation: `risk_manager.py:KellyCriterion`

2. **Almgren & Chriss (2001)** - Market impact model
   - Implementation: `advanced_engine.py:AlmgrenChrissSlippage`

3. **Jorion, P. (2007)** - Value at Risk methodology
   - Implementation: `risk_manager.py:ValueAtRisk`

4. **Engle & Granger (1987)** - Cointegration testing
   - Implementation: `advanced_engine.py:PriceHistoryTracker.test_cointegration`

5. **Sortino & Price (1994)** - Downside risk framework
   - Implementation: `risk_manager.py:PerformanceMetrics.calculate_sortino_ratio`

## Safety Features

1. **Paper Trading Default** - No real money at risk
2. **Circuit Breakers** - Auto-disconnect failing exchanges
3. **Rate Limiting** - Prevent API bans
4. **Daily Loss Limits** - Stop trading if threshold hit
5. **Maximum Drawdown** - Reduce risk during losses
6. **Position Constraints** - Never risk more than configured limits
7. **Score Thresholds** - Only execute high-quality opportunities (>0.6 score)

## Production Readiness Checklist

Before going live:

- [ ] Run in paper trading mode for 2+ weeks
- [ ] Verify ML scores make sense (check factor breakdowns)
- [ ] Confirm position sizes are appropriate (Kelly vs constraints)
- [ ] Monitor Sharpe ratio > 1.5 consistently
- [ ] Check VaR aligns with risk tolerance
- [ ] Ensure circuit breakers are working (check logs)
- [ ] Validate execution times < 200ms
- [ ] Review profit factor > 1.5

## Monitoring

Watch the 1-minute statistics output:

```
SYSTEM STATISTICS (1-minute update)
Opportunities:
  Detected:           142
  Scored (ML):        1847
  Executed:           23

Execution:
  Total Attempts:     23
  Success Rate:       95.7%
  Avg Time:           91ms
  Total Profit:       $34.21

Portfolio:
  Capital:            $10,034.21
  Win Rate:           60.9%
  Sharpe Ratio:       2.14
  Max Drawdown:       2.3%
  VaR (95%):          $12.34
```

## Troubleshooting

**No opportunities detected:**
- Normal! Profitable arbitrage is rare
- ML scoring filters out low-quality opportunities
- Lower `min_spread_percent` to see more (but lower quality)

**Position sizes too small:**
- Kelly Criterion is conservative (0.25x safety factor)
- Increase `max_position_usd` if comfortable
- Check win rate - low win rate = smaller positions

**High risk scores:**
- Volatility is high
- Win rate has dropped
- System auto-reduces position sizes

**Circuit breakers opening:**
- Exchange connectivity issues
- Will auto-recover after timeout
- Check exchange status pages

## Next Steps

1. **Collect Data** - Run for 1-2 weeks to build history
2. **Analyze Performance** - Review Sharpe, win rate, drawdowns
3. **Tune Parameters** - Adjust ML weights if needed
4. **Scale Gradually** - Increase position sizes slowly
5. **Monitor Continuously** - Watch for degradation

## Code Quality

The advanced system includes:
- ✅ Comprehensive type hints
- ✅ Detailed docstrings
- ✅ 500+ lines of tests
- ✅ Error handling and logging
- ✅ Research citations
- ✅ Production-grade patterns

## Support

For issues or questions:
1. Check logs in `data/logs/arbitrage.log`
2. Run tests: `pytest tests/test_advanced_features.py -v`
3. Review test output for failures
4. Check database for stored opportunities

---

**This system represents state-of-the-art in automated trading. All features are fully implemented and tested.**
