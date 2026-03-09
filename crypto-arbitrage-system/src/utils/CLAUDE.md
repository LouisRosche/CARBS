# src/utils — Security and Infrastructure Utilities

## Purpose
Shared utilities: encrypted credential management, Redis caching, Prometheus metrics.

## Key Files
- `credentials.py` — Fernet symmetric encryption for API key storage in memory
- `cache.py` — Redis client wrapper with TTL enforcement
- `metrics.py` — Prometheus Counter/Gauge/Histogram registration

## Security Rules (CRITICAL)
- `credentials.py`: The Fernet key is derived at runtime from env vars — NEVER hardcode it
- Credentials are stored encrypted in memory; decrypted only at point of use
- NEVER log decrypted credentials — structlog must redact sensitive fields
- Use `SecretStr` from pydantic for any credential-bearing fields

## Cache Rules
- Redis TTL for order book data: **exactly 1 second** — do not modify
- All cache keys must be namespaced: `carbs:<exchange>:<symbol>:<data_type>`
- Cache misses must be logged at DEBUG level, never silently ignored

## Metrics Registration
```python
# Register metrics at module level (not inside functions)
ARBITRAGE_OPPORTUNITIES = Counter(
    "carbs_arbitrage_opportunities_total",
    "Total arbitrage opportunities detected",
    ["exchange_pair", "symbol"]
)
```
- Do not create duplicate metric names — check `metrics.py` before adding new ones
- All metrics must include relevant labels for Grafana filtering
