# Contributing to CARBS (Crypto Arbitrage System)

Thank you for considering contributing to CARBS! This document provides guidelines for contributing code, documentation, and other improvements.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [Code Standards](#code-standards)
5. [Testing Requirements](#testing-requirements)
6. [Pull Request Process](#pull-request-process)
7. [Coding Patterns](#coding-patterns)
8. [Documentation Standards](#documentation-standards)
9. [Commit Message Guidelines](#commit-message-guidelines)
10. [Issue Reporting](#issue-reporting)

---

## Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

---

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose
- Git
- Basic understanding of async Python
- Familiarity with cryptocurrency trading concepts (helpful but not required)

### First Contributions

Good first issues for new contributors:
- Documentation improvements
- Adding test cases
- Fixing typos or broken links
- Adding type hints where missing
- Improving error messages

Look for issues tagged with `good-first-issue` or `help-wanted`.

---

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/CARBS.git
cd CARBS/crypto-arbitrage-system
```

### 2. Set Up Environment

```bash
# Create virtual environment and install dependencies
make setup

# Or manually:
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

### 3. Start Infrastructure

```bash
# Start PostgreSQL, Redis, and other services
make start

# Wait 30 seconds for containers to be ready, then:
make db-init
```

### 4. Run Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_engine.py -v

# Run with coverage
pytest --cov=src --cov-report=html
```

### 5. Set Up Pre-Commit Hooks (Optional but Recommended)

```bash
pip install pre-commit
pre-commit install
```

---

## Code Standards

### Python Version

- **Minimum**: Python 3.11
- Use modern Python features (match/case, type hints, async/await)

### Code Style

We use these tools to maintain code quality:

- **Black**: Code formatting (line length: 120)
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking

Run all formatters:
```bash
make format  # Runs black and isort
make lint    # Runs flake8 and mypy
```

### Type Hints

- **Required** for all public functions and methods
- **Required** for function parameters and return types
- Use `typing` module for complex types
- Use `Decimal` for financial calculations (never `float`)

Example:
```python
from decimal import Decimal
from typing import Optional, List, Tuple

async def calculate_spread(
    buy_price: Decimal,
    sell_price: Decimal,
    fees: Optional[Decimal] = None
) -> Tuple[Decimal, Decimal]:
    """
    Calculate spread between buy and sell prices.

    Args:
        buy_price: Price to buy at
        sell_price: Price to sell at
        fees: Optional fee percentage as decimal

    Returns:
        Tuple of (gross_spread, net_spread)
    """
    gross_spread = (sell_price - buy_price) / buy_price

    if fees:
        net_spread = gross_spread - (fees * Decimal('2'))  # Buy and sell fees
    else:
        net_spread = gross_spread

    return gross_spread, net_spread
```

### Async/Await

- Use `async def` for all I/O-bound operations (network, database, file I/O)
- Use `await` for async calls
- Use `asyncio.gather()` for concurrent operations
- Never block the event loop with synchronous I/O

### Docstrings

- **Required** for all public modules, classes, and functions
- Use Google-style docstrings
- Include examples for complex functions
- Document exceptions that may be raised

Example:
```python
def estimate_slippage(orderbook: OrderBook, size: Decimal) -> Decimal:
    """
    Estimate slippage for a given order size based on orderbook depth.

    This implements volume-weighted average price (VWAP) calculation
    across multiple orderbook levels.

    Args:
        orderbook: Current orderbook state
        size: Order size in USD

    Returns:
        Estimated slippage as decimal (e.g., 0.001 = 0.1%)

    Raises:
        ValueError: If size is negative

    Example:
        >>> ob = OrderBook(...)
        >>> slippage = estimate_slippage(ob, Decimal('1000'))
        >>> print(f"Slippage: {slippage * 100:.2f}%")
        Slippage: 0.15%
    """
    pass
```

---

## Testing Requirements

### Test Coverage

- **All new features** must include tests
- **All bug fixes** must include regression tests
- Target: **>80% code coverage** for new code
- Run mutation tests periodically: `mutmut run`

### Test Types

1. **Unit Tests**: Test individual functions/classes
   - Fast (<10ms per test)
   - No external dependencies
   - Use mocks for external services

2. **Integration Tests**: Test component interactions
   - Test with real PostgreSQL and Redis (via Docker)
   - Verify data persistence
   - Test error handling

3. **Performance Tests**: Test latency requirements
   - Use `pytest-benchmark`
   - Verify <100ms end-to-end latency
   - See `tests/test_performance.py`

4. **Chaos Tests**: Test resilience
   - Simulate network failures
   - Test graceful degradation
   - See `tests/test_chaos.py`

### Writing Good Tests

```python
import pytest
from decimal import Decimal
from unittest.mock import Mock, AsyncMock

class TestSpreadCalculation:
    """Test spread calculation logic"""

    def test_simple_spread_calculation(self):
        """Basic spread calculation without fees"""
        buy_price = Decimal('100.00')
        sell_price = Decimal('101.00')

        gross_spread, net_spread = calculate_spread(buy_price, sell_price)

        assert gross_spread == Decimal('0.01')  # 1%
        assert net_spread == Decimal('0.01')

    def test_spread_with_fees(self):
        """Spread calculation including fees"""
        buy_price = Decimal('100.00')
        sell_price = Decimal('101.00')
        fees = Decimal('0.001')  # 0.1% per trade

        gross_spread, net_spread = calculate_spread(buy_price, sell_price, fees)

        assert gross_spread == Decimal('0.01')
        assert net_spread == Decimal('0.008')  # 1% - (0.1% * 2)

    @pytest.mark.asyncio
    async def test_async_orderbook_fetch(self):
        """Test async orderbook fetching with mocks"""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_order_book = AsyncMock(return_value={
            'bids': [[100.0, 1.5]],
            'asks': [[101.0, 1.5]]
        })

        result = await mock_exchange.fetch_order_book('BTC/USDT')

        assert result is not None
        assert 'bids' in result
        mock_exchange.fetch_order_book.assert_called_once_with('BTC/USDT')
```

---

## Pull Request Process

### Before Submitting

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Write tests** for your changes

3. **Ensure all tests pass**:
   ```bash
   make test
   ```

4. **Format code**:
   ```bash
   make format
   make lint
   ```

5. **Update documentation**:
   - Update relevant `.md` files
   - Update docstrings
   - Add examples if helpful

6. **Update CHANGELOG.md**:
   - Add entry under `[Unreleased]`
   - Follow Keep a Changelog format

### Submitting the PR

1. **Push to your fork**:
   ```bash
   git push origin feature/my-new-feature
   ```

2. **Create Pull Request** on GitHub

3. **Fill out PR template** with:
   - **Description**: What does this PR do?
   - **Motivation**: Why is this change needed?
   - **Testing**: How was this tested?
   - **Checklist**: Confirm all items completed

### PR Review Process

- **Code Review**: At least one maintainer approval required
- **CI Checks**: All CI checks must pass (lint, test, security)
- **Documentation**: Documentation must be updated
- **Tests**: Tests must pass with >80% coverage for new code

### After PR Merge

- Delete your feature branch
- Pull latest main: `git pull upstream main`
- Celebrate! 🎉

---

## Coding Patterns

### Error Handling

Use specific exceptions, never bare `except`:

```python
# Good
try:
    result = await exchange.fetch_order_book('BTC/USDT')
except ConnectionError as e:
    logger.error(f"Exchange connection failed: {e}")
    return None
except asyncio.TimeoutError:
    logger.warning("Order book fetch timed out")
    return None

# Bad
try:
    result = await exchange.fetch_order_book('BTC/USDT')
except:  # Never do this!
    return None
```

### Logging

Use structured logging with appropriate levels:

```python
import logging
logger = logging.getLogger(__name__)

# Debug: Detailed diagnostic information
logger.debug(f"Fetching orderbook for {symbol} from {exchange}")

# Info: General informational messages
logger.info(f"Detected opportunity: {spread:.2f}% spread on {symbol}")

# Warning: Something unexpected but handled
logger.warning(f"Exchange {exchange} returned stale data (age: {age}s)")

# Error: Error that should be investigated
logger.error(f"Failed to execute trade: {error}", exc_info=True)

# Critical: System is in bad state
logger.critical(f"Database connection lost, halting trading")
```

### Decimal Precision

Always use `Decimal` for financial calculations:

```python
from decimal import Decimal

# Good
price = Decimal('67543.21')
amount = Decimal('0.01')
total = price * amount  # Exact: 675.4321

# Bad
price = 67543.21  # Float - precision errors!
amount = 0.01
total = price * amount  # May not be exact
```

### Configuration

Use config objects, not global variables:

```python
# Good
class Config:
    trading: TradingConfig
    exchanges: Dict[str, ExchangeConfig]

def process(config: Config):
    if config.trading.mode == 'paper':
        ...

# Bad
TRADING_MODE = 'paper'  # Global variable

def process():
    global TRADING_MODE
    if TRADING_MODE == 'paper':
        ...
```

---

## Documentation Standards

### README Updates

- Keep README concise and focused on getting started
- Move detailed docs to `/docs` folder
- Update Quick Start if setup changes
- Keep examples current

### Inline Documentation

- Comment complex algorithms
- Reference academic papers where applicable
- Explain "why" not just "what"
- Use TODO/FIXME/NOTE markers appropriately

```python
# TODO: Optimize this for large orderbooks (>100 levels)
# FIXME: Race condition when multiple threads access cache
# NOTE: This uses Almgren-Chriss model (see RESEARCH.md)
```

---

## Commit Message Guidelines

Follow Conventional Commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code restructuring
- `perf`: Performance improvements
- `test`: Adding tests
- `chore`: Maintenance tasks

### Examples

```
feat(engine): add triangle arbitrage detection

Implement triangle arbitrage across three trading pairs with
fee and slippage calculations. Uses graph traversal to find
profitable cycles.

Closes #123
```

```
fix(security): prevent API key exposure in logs

API keys were being logged in debug mode. Now properly
redacted in all log outputs.

Fixes #456
```

---

## Issue Reporting

### Bug Reports

Include:
- **Steps to reproduce**
- **Expected behavior**
- **Actual behavior**
- **Environment** (OS, Python version, Docker version)
- **Logs** (relevant excerpts)
- **Configuration** (sanitized, no API keys!)

### Feature Requests

Include:
- **Use case**: What problem does this solve?
- **Proposed solution**: How should it work?
- **Alternatives considered**: What other approaches did you think about?
- **Additional context**: Any mockups, examples, or references

### Security Issues

**DO NOT** open public issues for security vulnerabilities.
See [SECURITY.md](SECURITY.md) for responsible disclosure process.

---

## Questions?

- Check [docs/](docs/) folder for detailed documentation
- Read [ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design
- See [RUNBOOK.md](docs/RUNBOOK.md) for operational procedures
- Open a GitHub Discussion for general questions
- Join our community chat (if available)

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
