# Contributing to CARBS

Thank you for considering contributing to CARBS. This document covers development setup, code standards, architecture, and the contribution process.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Development Setup](#development-setup)
3. [Architecture](#architecture)
4. [Code Standards](#code-standards)
5. [Testing](#testing)
6. [Configuration Reference](#configuration-reference)
7. [Pull Request Process](#pull-request-process)
8. [Governance](#governance)

---

## Code of Conduct

We are committed to a welcoming, professional environment. Be respectful, provide constructive feedback, and focus on technical merit. Personal attacks, trolling, and publishing others' private information are not tolerated. Violations may result in warnings, temporary bans, or permanent bans. Report concerns to project maintainers via GitHub Issues.

---

## Development Setup

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git
- Basic understanding of async Python

### Fork, Clone, and Install

```bash
git clone https://github.com/YOUR_USERNAME/CARBS.git
cd CARBS/crypto-arbitrage-system

# Create virtual environment and install
make setup
# Or manually:
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
cp .env.example .env
```

### Start Infrastructure and Run Tests

```bash
make start       # Start PostgreSQL, Redis, Prometheus
make db-init     # Initialize database
make test        # Run full test suite
```

### Pre-Commit Hooks (Optional)

```bash
pip install pre-commit
pre-commit install
```

---

## Architecture

### System Overview

Async-first architecture optimized for sub-100ms latency.

```
Exchange APIs -> CCXT Pro (WebSocket) -> Engine -> Redis Cache (1s TTL)
                                             |
                                      Opportunity Detection
                                             |
                                      PostgreSQL/TimescaleDB
                                             |
                                      Grafana Analytics
```

### Core Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Arbitrage Engine | `src/core/advanced_engine.py` | ML scoring, slippage estimation, cointegration |
| Execution Engine | `src/core/execution_engine.py` | Circuit breakers, rate limiting, retry logic |
| Risk Manager | `src/core/risk_manager.py` | Kelly Criterion, VaR, Sharpe/Sortino ratios |
| Exchange Adapters | `src/exchanges/` | CCXT Pro adapters (Binance, MEXC, KuCoin) |
| Database Layer | `src/database/` | TimescaleDB via asyncpg, connection pooling |
| Cache Layer | `src/utils/cache.py` | Redis with 1s TTL, ~80% API call reduction |
| Health API | `src/api/` | FastAPI liveness/readiness/health probes |
| Compliance | `src/compliance/` | Tax, Form 1099-DA, Missouri tax calculator |

### Key Algorithms

- **ML Scoring**: 6-factor composite (spread 35%, liquidity 25%, volatility 15%, exchange quality 15%, timing 10%)
- **Slippage**: Almgren-Chriss market impact model with multi-level orderbook consumption
- **Position Sizing**: Kelly Criterion with safety factor, capped at 10-25%
- **Risk**: VaR (95%/99%), Expected Shortfall (CVaR), maximum drawdown tracking
- **Execution**: Circuit breaker (CLOSED -> OPEN -> HALF_OPEN), exponential backoff retry

### Architecture Invariants

- Circuit breaker in `execution_engine.py` wraps all exchange calls -- do NOT remove
- Kelly Criterion position sizing is mandatory for live trades
- Health endpoints (`/live`, `/ready`, `/health`) must remain functional
- All exchange I/O is async (`async def` throughout)

---

## Code Standards

### Formatting and Linting

```bash
make format    # black (120 chars) + isort
make lint      # flake8 + mypy
```

### Type Hints (Required)

All public functions and methods must have type hints. Use `Decimal` for financial calculations, never `float`.

```python
from decimal import Decimal
from typing import Optional, Tuple

async def calculate_spread(
    buy_price: Decimal,
    sell_price: Decimal,
    fees: Optional[Decimal] = None
) -> Tuple[Decimal, Decimal]:
    """Calculate spread between buy and sell prices."""
    gross_spread = (sell_price - buy_price) / buy_price
    net_spread = gross_spread - (fees * Decimal('2')) if fees else gross_spread
    return gross_spread, net_spread
```

### Async/Await

- Use `async def` for all I/O-bound operations (network, database, file I/O)
- Use `asyncio.gather()` for concurrent operations
- Never block the event loop with synchronous I/O

### DateTime Handling (CRITICAL)

**All datetime objects must be timezone-aware. Naive datetimes cause crashes.**

```python
from datetime import datetime, timezone

# CORRECT
trade_time = datetime.now(timezone.utc)
acquisition_date = datetime(2025, 8, 1, tzinfo=timezone.utc)

# WRONG - will crash in compliance modules
trade_time = datetime.now()  # No timezone!
```

Modules requiring timezone-aware datetimes: `missouri_tax.py`, `form_1099_da.py`, `cost_basis.py`, `database/trades.py`.

### Logging

Use the standard `logging` module. Never use `print()` in `src/`.

```python
import logging
logger = logging.getLogger(__name__)

logger.debug(f"Fetching orderbook for {symbol} from {exchange}")
logger.info(f"Detected opportunity: {spread:.2f}% spread on {symbol}")
logger.warning(f"Exchange {exchange} returned stale data (age: {age}s)")
logger.error(f"Failed to execute trade: {error}", exc_info=True)
```

### Error Handling

Use specific exceptions, never bare `except`:

```python
try:
    result = await exchange.fetch_order_book('BTC/USDT')
except ConnectionError as e:
    logger.error(f"Exchange connection failed: {e}")
    return None
except asyncio.TimeoutError:
    logger.warning("Order book fetch timed out")
    return None
```

### Docstrings

Required for all public modules, classes, and functions. Use Google-style docstrings.

### Import Paths

All imports must use the `src.` prefix:

```python
# CORRECT
from src.compliance import MissouriTaxCalculator
from src.exchanges import BinanceExchange

# WRONG
from compliance import MissouriTaxCalculator
```

### Anti-Patterns to Avoid

- Do NOT add synchronous blocking calls inside async functions
- Do NOT store credentials in `config/config.yaml` -- `.env` only
- Do NOT hardcode exchange symbols -- use `config.symbols` list
- Do NOT import from `src.advanced_main` -- use module-level imports

---

## Testing

### Running Tests

```bash
make test                                    # Full suite with coverage
pytest tests/test_compliance.py -v           # Specific file
pytest --cov=src --cov-report=html           # Coverage report
pytest -m unit                               # Only unit tests
pytest -m integration                        # Only integration tests
```

### Requirements

- All new features must include tests
- All bug fixes must include regression tests
- Target: >80% code coverage for new code
- Coverage >= 50% required (per CLAUDE.md)
- Mock exchanges -- never call live APIs in tests
- Use `pytest-asyncio` with `asyncio_mode = "auto"`

### Test Types

| Type | Speed | Dependencies | Example |
|------|-------|--------------|---------|
| Unit | <10ms | None (mocked) | `test_compliance.py` |
| Integration | Variable | PostgreSQL, Redis | `test_integration.py` |
| Performance | Variable | Benchmarks | `test_performance.py` |
| Chaos | Variable | Simulated failures | `test_chaos.py` |

### Writing Tests

```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock

class TestSpreadCalculation:
    def test_simple_spread(self):
        buy_price = Decimal('100.00')
        sell_price = Decimal('101.00')
        gross, net = calculate_spread(buy_price, sell_price)
        assert gross == Decimal('0.01')

    @pytest.mark.asyncio
    async def test_async_orderbook_fetch(self):
        mock_exchange = AsyncMock()
        mock_exchange.fetch_order_book = AsyncMock(return_value={
            'bids': [[100.0, 1.5]], 'asks': [[101.0, 1.5]]
        })
        result = await mock_exchange.fetch_order_book('BTC/USDT')
        assert 'bids' in result
```

### Common Fixtures (conftest.py)

`sample_trade_data`, `sample_orderbook_data`, `mock_db_manager`, `mock_exchange_client`, `mock_redis`, `temp_data_dir`, `sample_config`

---

## Configuration Reference

### Precedence (Highest to Lowest)

1. Environment variables
2. `.env` file
3. `config/config.yaml`
4. Code defaults

### Secrets Management

```bash
# Generate master key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Protect .env
chmod 600 .env

# .gitignore already includes: .env, *.key, *.pem, credentials.json
```

### Validation

On startup, CARBS validates: required variables set, numeric ranges valid, API key format correct, exchange names valid, symbol format correct (BASE/QUOTE). Application will not start if validation fails.

---

## Pull Request Process

### Before Submitting

1. Create a feature branch: `git checkout -b feature/my-new-feature`
2. Write tests for your changes
3. Ensure all tests pass: `make test`
4. Format code: `make format && make lint`
5. Update documentation and docstrings
6. Update CHANGELOG.md under `[Unreleased]`

### PR Requirements

- At least one maintainer approval
- All CI checks pass (lint, type-check, tests, security)
- Tests pass with >80% coverage for new code
- Documentation updated

### Commit Messages

Follow Conventional Commits:

```
feat(engine): add triangle arbitrage detection
fix(security): prevent API key exposure in logs
docs(readme): update quick start instructions
test(risk): add Kelly Criterion edge case tests
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`

### Issue Reporting

**Bugs**: Steps to reproduce, expected vs actual behavior, environment, sanitized logs.
**Features**: Use case, proposed solution, alternatives considered.
**Security**: DO NOT open public issues. See [SECURITY.md](SECURITY.md).

---

## Governance

### Project Status

- **Status**: Active Development
- **Version**: 1.0.0
- **Primary Maintainer**: Louis Rosche (@LouisRosche)
- **License**: MIT

### Response Times (Targets)

| Issue Type | Response | Resolution |
|------------|----------|------------|
| Security vulnerability | 24 hours | 72 hours |
| Critical bug | 48 hours | 1 week |
| Major bug | 1 week | 2 weeks |
| Feature request | 1 week (eval) | Variable |

### Versioning

[Semantic Versioning](https://semver.org/): MAJOR (breaking), MINOR (features), PATCH (fixes).

### Release Checklist

- [ ] All tests pass
- [ ] CHANGELOG.md updated
- [ ] Version bumped in setup.py, __init__.py
- [ ] Security scan clean
- [ ] Documentation updated
- [ ] Git tag: `git tag v1.X.X`

### Decision Making

The primary maintainer has final authority on code merges, releases, and project direction. Community input is valued through Issues, Discussions, and PRs. Major decisions (breaking changes, architecture shifts) have a 2-week feedback period.

---

By contributing, you agree that your contributions will be licensed under the MIT License.
