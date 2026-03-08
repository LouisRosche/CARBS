# src/exchanges — Exchange Adapter Module

## Purpose
CCXT Pro WebSocket adapters for Binance, Coinbase, Kraken, OKX, and Bybit.
Each adapter wraps raw CCXT calls with credential management and error handling.

## Patterns
- Adapters inherit from a base class with circuit breaker integration
- Credentials loaded via `src/utils/credentials.py` (Fernet-encrypted)
- WebSocket connections use CCXT Pro's `watch_order_book` and `watch_ticker`
- Reconnection logic uses exponential backoff (max 5 retries)

## Critical Rules
- NEVER store API keys in adapter classes — always read from encrypted store
- SSL verification MUST remain enabled on all connections
- Rate limiting is per-exchange; respect CCXT's built-in rate limiter
- Order book data cached in Redis with 1-second TTL — do not bypass

## Error Handling
```python
# Standard pattern for exchange calls
try:
    result = await exchange.fetch_ticker(symbol)
except ccxt.NetworkError as e:
    logger.warning("network_error", exchange=self.name, error=str(e))
    # Circuit breaker will handle retry logic
except ccxt.ExchangeError as e:
    logger.error("exchange_error", exchange=self.name, error=str(e))
    raise
```

## Testing
- Use `pytest-mock` to patch `ccxt.pro.<Exchange>` at the class level
- Never instantiate real exchange connections in tests
- Test both success paths and each exception type
