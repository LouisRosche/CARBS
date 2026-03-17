# src/exchanges — Exchange Adapter Module

## Purpose
CCXT Pro WebSocket adapters for **Binance** and **MEXC** (extensible to KuCoin, others).
The bot uses **ccxt.pro exchange objects directly** — there is no custom BaseExchange wrapper.

## Key Files
- `enums.py` — `OrderSide`, `OrderType`, `OrderStatus`
- `models.py` — `Ticker`, `OrderBook`, `Balance`, `Order`, `Trade` data models
- `rate_limiter.py` — Token bucket rate limiter
- `websocket_manager.py` — Standalone WebSocket management (BinanceWebSocket, MEXCWebSocket, KuCoinWebSocket). Currently unused by `advanced_main.py` which uses ccxt.pro's `watch_order_book` directly. Candidate for future integration.
- `exceptions.py` — `ExchangeError` custom exception

## Architecture
- `advanced_main.py` instantiates ccxt.pro exchange classes directly (e.g., `ccxt.pro.binance()`)
- Orderbook data flows through ccxt.pro's `watch_order_book` WebSocket API
- No custom adapter layer between business logic and ccxt.pro

## Critical Rules
- NEVER store API keys in code — always read from `.env` via encrypted store
- SSL verification MUST remain enabled on all connections
- Rate limiting is per-exchange; respect CCXT's built-in rate limiter

## Error Handling
```python
# Standard pattern for exchange calls
try:
    result = await exchange.fetch_ticker(symbol)
except ccxt.NetworkError as e:
    logger.warning("network_error", exchange=name, error=str(e))
    # Circuit breaker handles retry logic
except ccxt.ExchangeError as e:
    logger.error("exchange_error", exchange=name, error=str(e))
    raise
```

## Testing
- Use `pytest-mock` to patch `ccxt.pro.<Exchange>` at the class level
- Never instantiate real exchange connections in tests
- Test both success paths and each exception type
