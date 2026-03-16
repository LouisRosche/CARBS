# CARBS - Crypto Arbitrage Bot System

Paper-trading cryptocurrency arbitrage detection and execution platform. Monitors price discrepancies across exchanges and identifies profitable spread opportunities.

**Status:** Paper trading only. Not validated for live trading with real capital.

## Quick Start

```bash
cd crypto-arbitrage-system
cp .env.example .env        # Configure API keys
make setup                  # Create venv + install deps
make start                  # Start postgres, redis, prometheus
python scripts/init_db.py   # Initialize database
python -m src.main          # Run the bot (paper mode)
```

## Architecture

```
crypto-arbitrage-system/
  src/core/         # Arbitrage engine, execution, risk management
  src/exchanges/    # CCXT Pro adapters (Binance, MEXC)
  src/api/          # FastAPI health/metrics endpoints
  src/database/     # PostgreSQL models (asyncpg)
  src/utils/        # Credentials (Fernet), cache (Redis), metrics
  src/ml/           # Optional ML pipeline (requires torch)
  tests/            # pytest test suite
  config/           # Runtime configuration
```

## Key Design Decisions

- **Async-first**: All exchange I/O uses asyncio + ccxt.pro WebSockets
- **Circuit breakers**: All exchange calls wrapped for fault tolerance
- **Kelly Criterion**: Position sizing capped at 10% of capital
- **Paper by default**: Live trading requires explicit `mode: live` in config

## Risk Disclaimer

This software is for educational and research purposes. Cryptocurrency trading carries significant financial risk. Past performance does not guarantee future results. Never trade with money you cannot afford to lose.

## Docs

- [Getting Started](GETTING_STARTED.md)
- [Configuration](crypto-arbitrage-system/CONFIGURATION.md)
- [Deployment](crypto-arbitrage-system/DEPLOYMENT.md)
- [Security](crypto-arbitrage-system/SECURITY.md)
- [Architecture](crypto-arbitrage-system/docs/ARCHITECTURE.md)
- [Exchange Guide](crypto-arbitrage-system/docs/EXCHANGE_GUIDE.md)
- [API Keys Setup](crypto-arbitrage-system/docs/API_KEYS.md)

## License

See [LICENSE](crypto-arbitrage-system/LICENSE).
