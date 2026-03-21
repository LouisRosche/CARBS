# src/utils — Security and Infrastructure Utilities

## Purpose
Shared utilities: encrypted credential management, Redis caching, Prometheus metrics.

## Key Files
- `secure_credentials.py` — `SecureCredentialStore` (Fernet encryption, PBKDF2 key derivation, 600k iterations) and `SecureString` (per-value encrypted wrapper). `cryptography` package is a hard requirement — no XOR fallback.
- `cache.py` — `RedisCache` (async Redis client with TLS support, retry logic), `TokenBlacklist`, `SessionStore`
- `metrics.py` — `MetricsCollector` (basic Prometheus Counter/Gauge/Histogram registration)
- `error_handling.py` — Centralized error handling utilities
- `resilience.py` — Resilience patterns (retry, backoff)

## Security Rules (CRITICAL)
- `secure_credentials.py`: The Fernet key is derived at runtime from env vars — NEVER hardcode it
- Credentials are stored encrypted in memory; decrypted only at point of use
- NEVER log decrypted credentials — logging must redact sensitive fields

## Cache Rules
- `RedisCache` accepts TTL as a parameter on `set()` calls — callers are responsible for passing correct TTL
- Order book data callers should use `ttl=1` (1 second)
- All cache keys should be namespaced: `carbs:<exchange>:<symbol>:<data_type>`
- `TokenBlacklist` uses key prefix `carbs:token:blacklist`
- `SessionStore` uses key prefix `carbs:session:` and `carbs:user_sessions:`

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
- Note: `health.py` contains an extended `PrometheusMetrics` class with 25+ additional metrics
