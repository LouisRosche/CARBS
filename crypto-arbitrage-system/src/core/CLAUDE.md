# src/core — Arbitrage Engine Module

## Purpose
Core arbitrage detection, execution engine, and risk management. This is the most
safety-critical part of the codebase.

## Key Files
- `engine.py` — `ArbitrageEngine`: spread detection, opportunity scoring. Data models: `Opportunity` and `OrderBook` (`@dataclass`)
- `execution_engine.py` — `ExecutionEngine`: order placement with `CircuitBreaker` pattern (CLOSED/OPEN/HALF_OPEN states)
- `risk_manager.py` — `RiskManager` + `KellyCriterion`: position sizing (cap: 10%), VaR, position limits
- `advanced_engine.py` — `AdvancedArbitrageEngine`: multi-exchange engine with cointegration analysis
- `triangle_arbitrage.py` — Triangle arbitrage path detection
- `balance_manager.py` — Balance tracking and validation
- `antifragile.py` — Antifragile trading strategies (Kelly cap: 25%)
- `graceful_shutdown.py` — Async shutdown coordination
- `state_manager.py` — Engine state persistence

## Invariants (DO NOT VIOLATE)
- Circuit breaker state must be checked BEFORE every exchange API call
- Kelly fraction cap: 10% in `risk_manager.py`, 25% in `antifragile.py`
- `min_spread_percent` from config must gate all opportunity detection

## Patterns
- All execution functions are `async def`
- Data models use `@dataclass` (not pydantic)
- Logging via standard `logging` module (`logger = logging.getLogger(__name__)`)
- Log all circuit breaker state changes at WARNING level

## Testing This Module
```bash
pytest tests/core/ -v
# All exchange calls MUST be mocked via pytest-mock
# Test circuit breaker open/closed/half-open states explicitly
```
