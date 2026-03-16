# CARBS - Claude Code Memory

## Project
Crypto Arbitrage Bot System (Python 3.11+). Paper-trading default; live trading requires explicit config.

## Critical Safety Rules
- NEVER enable live trading (`mode: live`) without explicit user confirmation
- NEVER commit API keys or secrets — use `.env` (gitignored)
- NEVER bypass SSL verification on exchange connections
- Risk disclaimer MUST remain in README.md and be visible to users

## Repository Layout
```
/                           ← Root: docs, CLAUDE.md, AGENTS.md
/crypto-arbitrage-system/   ← Main Python package (work here)
  src/core/                 ← Arbitrage engine, execution, risk management
  src/exchanges/            ← CCXT Pro adapters (Binance, MEXC, KuCoin)
  src/api/                  ← FastAPI health/metrics endpoints
  src/database/             ← PostgreSQL models via asyncpg
  src/utils/                ← Credentials (Fernet), cache (Redis), metrics (Prometheus)
  tests/                    ← pytest test suite
  config/config.yaml        ← Runtime config (trading mode, exchanges, symbols)
```

## Build & Test Commands
```bash
cd crypto-arbitrage-system
make setup          # Create venv + install dependencies
make start          # docker compose up -d (postgres, redis, prometheus)
make test           # pytest tests/ -v --cov=src  (coverage ≥50% required)
make lint           # flake8 + mypy
make format         # black + isort (line-length=120)
```

## Code Conventions
- **Python style**: black (120 chars), isort, type hints required for public functions
- **Async**: All exchange I/O is async (asyncio + ccxt.pro); use `async def` throughout
- **Logging**: standard `logging` module — never use `print()` in src/
- **Data models**: `@dataclass` for internal data structures; pydantic v2 for external API boundaries
- **Tests**: pytest-asyncio, `asyncio_mode = "auto"`; mock exchanges, never call live APIs in tests
- **Secrets**: Fernet encryption via `src/utils/secure_credentials.py` — never plaintext

## Architecture Invariants
- Circuit breaker in `execution_engine.py` wraps exchange calls — do NOT remove
- Kelly Criterion position sizing is mandatory for live trades (cap: 10% in risk_manager, 25% in antifragile)
- Health endpoints (`/live`, `/ready`, `/health`) must remain functional

## Anti-Patterns to Avoid
- Do NOT add synchronous blocking calls inside async functions
- Do NOT store credentials in `config/config.yaml` — `.env` only
- Do NOT hardcode exchange symbols; use `config.symbols` list
- Do NOT import from `src.advanced_main` — use module-level imports

## Module Nesting (Progressive Disclosure)
- `src/core/CLAUDE.md` — arbitrage engine specifics
- `src/exchanges/CLAUDE.md` — exchange adapter patterns
- `src/utils/CLAUDE.md` — security and credential handling

## Key Dependencies
| Package | Purpose |
|---------|---------|
| ccxt==4.5.28 | Exchange WebSocket connectivity |
| asyncpg==0.29.0 | PostgreSQL async driver |
| redis==5.0.1 | Orderbook caching |
| pydantic==2.5.3 | Data validation |
| cryptography==41.0.7 | Fernet credential encryption |
| prometheus-client==0.19.0 | Metrics export |
