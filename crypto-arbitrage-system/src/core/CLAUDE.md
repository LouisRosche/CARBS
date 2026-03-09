# src/core — Arbitrage Engine Module

## Purpose
Core arbitrage detection, execution engine, and risk management. This is the most
safety-critical part of the codebase.

## Key Files
- `arbitrage.py` — Spread detection, opportunity scoring (6-factor ML composite)
- `execution.py` — Order placement with circuit breaker pattern
- `risk.py` — Kelly Criterion sizing, VaR tracking, position limits

## Invariants (DO NOT VIOLATE)
- Circuit breaker state must be checked BEFORE every exchange API call
- Kelly fraction must be ≤ 0.25 for any single position (hardcoded safety cap)
- Slippage estimation (Almgren-Chriss) must run before order placement
- `min_spread_percent` from config must gate all opportunity detection

## Patterns
- All execution functions are `async def`
- Opportunity objects are pydantic v2 `BaseModel` instances
- Log all trade decisions with structlog at INFO level
- Log all circuit breaker state changes at WARNING level

## Testing This Module
```bash
pytest tests/core/ -v
# All exchange calls MUST be mocked via pytest-mock
# Test circuit breaker open/closed/half-open states explicitly
```
