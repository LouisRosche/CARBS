# CARBS Developer Guide

This guide provides technical implementation details for developers working with the CARBS codebase.

## Table of Contents

- [DateTime Handling](#datetime-handling)
- [Module Structure](#module-structure)
- [Testing](#testing)
- [Code Standards](#code-standards)

---

## DateTime Handling

### ⚠️ CRITICAL: Always Use Timezone-Aware Datetimes

**All datetime objects in CARBS MUST be timezone-aware. Naive datetimes will cause crashes.**

#### Why This Matters

The compliance and tax modules perform date-based calculations that depend on timezone information. Passing naive datetimes will result in `TypeError: can't compare offset-naive and offset-aware datetimes`.

#### Correct Usage

```python
from datetime import datetime, timezone

# ✅ CORRECT - Timezone-aware datetime (UTC)
trade_time = datetime.now(timezone.utc)
acquisition_date = datetime(2025, 8, 1, tzinfo=timezone.utc)

# ✅ CORRECT - Convert from timestamp
from_timestamp = datetime.fromtimestamp(1735670400, tz=timezone.utc)

# ❌ WRONG - Naive datetime (will crash)
trade_time = datetime.now()  # No timezone!
acquisition_date = datetime(2025, 8, 1)  # No timezone!
```

#### Modules That Require Timezone-Aware Datetimes

1. **`src/compliance/missouri_tax.py`** - All methods require timezone-aware dates
2. **`src/compliance/form_1099_da.py`** - Tax year calculations require timezone info
3. **`src/compliance/cost_basis.py`** - Short-term vs long-term holding period calculations
4. **`src/database/trades.py`** - Trade timestamps must be timezone-aware
5. **`src/database/balances.py`** - Balance snapshots use timezone-aware timestamps

#### Working with Exchange Data

Exchange APIs return timestamps in various formats. Always normalize to UTC:

```python
import ccxt
from datetime import datetime, timezone

# CCXT returns milliseconds since epoch
exchange_timestamp = 1735670400000

# ✅ Convert to timezone-aware datetime
trade_time = datetime.fromtimestamp(
    exchange_timestamp / 1000,  # Convert ms to seconds
    tz=timezone.utc
)

# When creating orders
order = {
    'timestamp': int(datetime.now(timezone.utc).timestamp() * 1000),  # ms
    'datetime': datetime.now(timezone.utc).isoformat()
}
```

#### Testing with Datetimes

All test fixtures and test data must use timezone-aware datetimes:

```python
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

def test_missouri_tax_calculation():
    """Test Missouri tax calculation with proper timezone handling"""
    from src.compliance.missouri_tax import MissouriTaxCalculator

    calc = MissouriTaxCalculator()

    # ✅ Use timezone-aware datetimes in tests
    pre_exemption_date = datetime(2025, 8, 1, tzinfo=timezone.utc)
    post_exemption_date = datetime(2025, 9, 1, tzinfo=timezone.utc)

    # Test pre-exemption period
    tax = calc.calculate_missouri_tax(Decimal('1000'), pre_exemption_date)
    assert tax == Decimal('54.00')  # 5.4% rate

    # Test post-exemption period
    tax = calc.calculate_missouri_tax(Decimal('1000'), post_exemption_date)
    assert tax == Decimal('0.00')  # 100% exempt
```

#### Common Pitfalls

```python
# ❌ WRONG - datetime.now() without timezone
now = datetime.now()  # Naive datetime!

# ❌ WRONG - Using .replace() on naive datetime
now = datetime.now().replace(tzinfo=timezone.utc)  # Better to use tz parameter

# ✅ CORRECT - Use tz parameter from the start
now = datetime.now(timezone.utc)

# ❌ WRONG - Comparing naive and aware datetimes
naive_dt = datetime(2025, 1, 1)
aware_dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
if naive_dt < aware_dt:  # TypeError!
    pass

# ✅ CORRECT - Both must be timezone-aware
dt1 = datetime(2025, 1, 1, tzinfo=timezone.utc)
dt2 = datetime(2025, 2, 1, tzinfo=timezone.utc)
if dt1 < dt2:  # Works!
    pass
```

#### Database Storage

PostgreSQL `TIMESTAMPTZ` columns automatically handle timezone conversion:

```python
import asyncpg
from datetime import datetime, timezone

# ✅ PostgreSQL stores all times in UTC internally
async with pool.acquire() as conn:
    # Python datetime with timezone → PostgreSQL TIMESTAMPTZ
    await conn.execute(
        'INSERT INTO trades (timestamp, symbol, price) VALUES ($1, $2, $3)',
        datetime.now(timezone.utc),  # Stored as UTC
        'BTC/USDT',
        Decimal('67000')
    )

    # Retrieved as timezone-aware datetime
    row = await conn.fetchrow('SELECT timestamp FROM trades WHERE id = $1', trade_id)
    timestamp = row['timestamp']  # Already timezone-aware!
```

#### Defensive Coding

If you're writing a function that accepts datetimes from external sources, validate timezone awareness:

```python
from datetime import datetime, timezone

def process_trade(timestamp: datetime, symbol: str, price: Decimal):
    """Process a trade with timestamp validation"""
    # Defensive check for timezone awareness
    if timestamp.tzinfo is None or timestamp.tzinfo.utcoffset(timestamp) is None:
        raise ValueError(
            f"Timestamp must be timezone-aware. Got naive datetime: {timestamp}. "
            f"Use datetime.now(timezone.utc) or add tzinfo=timezone.utc"
        )

    # Safe to proceed
    return calculate_metrics(timestamp, symbol, price)
```

---

## Module Structure

### Import Paths

All imports from the CARBS codebase must use the `src.` prefix:

```python
# ✅ CORRECT
from src.compliance import MissouriTaxCalculator, Form1099DAReconciler
from src.exchanges import BinanceExchange, MEXCExchange
from src.database import TradeRepository, BalanceRepository
from src.engine import ArbitrageEngine

# ❌ WRONG
from compliance import MissouriTaxCalculator  # Will fail in tests!
from exchanges import BinanceExchange  # Import error
```

### Project Structure

```
crypto-arbitrage-system/
├── src/                    # All source code (use 'src.' imports)
│   ├── compliance/         # Tax, regulatory, Form 1099-DA
│   ├── exchanges/          # Exchange implementations
│   ├── database/           # PostgreSQL repositories
│   ├── engine/             # Arbitrage detection logic
│   ├── risk/               # Risk management
│   ├── security/           # Encryption, audit logs
│   └── signals/            # Sentiment analysis, trading signals
├── tests/                  # Test suite (imports from src.)
│   ├── conftest.py         # Pytest configuration
│   └── test_*.py           # Test modules
├── config/                 # YAML configuration
├── docs/                   # Documentation
└── requirements.txt        # Dependencies
```

---

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/test_compliance.py

# Run with verbose output
python -m pytest tests/test_compliance.py -v

# Run with coverage
python -m pytest --cov=src --cov-report=html

# Run only unit tests
python -m pytest -m unit

# Run only integration tests
python -m pytest -m integration
```

### Test Markers

Use pytest markers to categorize tests:

```python
import pytest

@pytest.mark.unit
def test_tax_calculation():
    """Unit test for tax calculation logic"""
    pass

@pytest.mark.integration
async def test_database_trades():
    """Integration test requiring database"""
    pass

@pytest.mark.slow
async def test_full_arbitrage_cycle():
    """Long-running end-to-end test"""
    pass

@pytest.mark.security
def test_api_key_encryption():
    """Security-focused test"""
    pass
```

### Fixtures

Common fixtures are available in `tests/conftest.py`:

- `sample_trade_data` - Mock trade data
- `sample_orderbook_data` - Mock orderbook
- `mock_db_manager` - Mock database
- `mock_exchange_client` - Mock exchange API
- `mock_redis` - Mock Redis client
- `temp_data_dir` - Temporary directory for file tests
- `sample_config` - Test configuration

Example usage:

```python
def test_trade_processing(sample_trade_data, mock_db_manager):
    """Test using shared fixtures"""
    trade = process_trade(sample_trade_data)
    assert trade['status'] == 'completed'
```

---

## Code Standards

### Type Hints

Use type hints for all function signatures:

```python
from typing import List, Dict, Optional
from decimal import Decimal
from datetime import datetime

def calculate_profit(
    buy_price: Decimal,
    sell_price: Decimal,
    quantity: Decimal,
    fees: Optional[Decimal] = None
) -> Decimal:
    """Calculate profit with optional fees"""
    gross = (sell_price - buy_price) * quantity
    if fees:
        return gross - fees
    return gross
```

### Async/Await

Exchange and database operations must be async:

```python
import asyncio
from typing import List, Dict

async def fetch_orderbooks(symbols: List[str]) -> Dict[str, dict]:
    """Fetch multiple orderbooks concurrently"""
    tasks = [exchange.fetch_order_book(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    return {
        symbol: result
        for symbol, result in zip(symbols, results)
        if not isinstance(result, Exception)
    }
```

### Error Handling

Use specific exception types:

```python
from src.exchanges.exceptions import (
    ExchangeError,
    InsufficientBalance,
    RateLimitExceeded
)

async def execute_trade(exchange, order):
    """Execute trade with proper error handling"""
    try:
        result = await exchange.create_order(order)
        return result
    except InsufficientBalance as e:
        logger.error(f"Insufficient balance: {e}")
        return None
    except RateLimitExceeded as e:
        logger.warning(f"Rate limit hit, retrying in {e.retry_after}s")
        await asyncio.sleep(e.retry_after)
        return await execute_trade(exchange, order)
    except ExchangeError as e:
        logger.error(f"Exchange error: {e}")
        raise
```

### Logging

Use structured logging:

```python
import structlog

logger = structlog.get_logger(__name__)

async def process_arbitrage_opportunity(opp):
    """Process opportunity with structured logging"""
    logger.info(
        "processing_arbitrage",
        symbol=opp['symbol'],
        spread_percent=opp['spread_percent'],
        expected_profit=float(opp['expected_profit'])
    )

    try:
        result = await execute_arbitrage(opp)
        logger.info(
            "arbitrage_completed",
            trade_id=result['trade_id'],
            actual_profit=float(result['profit']),
            execution_time_ms=result['execution_time_ms']
        )
    except Exception as e:
        logger.error(
            "arbitrage_failed",
            error=str(e),
            symbol=opp['symbol']
        )
        raise
```

### Decimal Precision

Always use `Decimal` for financial calculations:

```python
from decimal import Decimal, ROUND_DOWN

# ✅ CORRECT - Use Decimal for money
price = Decimal('67000.00')
quantity = Decimal('0.1')
total = price * quantity  # Decimal('6700.00')

# ✅ CORRECT - Rounding
fee = (total * Decimal('0.001')).quantize(Decimal('0.01'), rounding=ROUND_DOWN)

# ❌ WRONG - Float precision errors
price = 67000.00  # float!
quantity = 0.1    # float!
total = price * quantity  # 6700.000000000001 (precision error!)
```

---

## Environment Variables

Required environment variables (set in `.env`):

```bash
# Trading Configuration
TRADING_MODE=paper          # paper | live
USER_JURISDICTION=US        # US | UK | EU | etc.

# Exchange API Keys
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
MEXC_API_KEY=your_key
MEXC_API_SECRET=your_secret

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/carbs
REDIS_URL=redis://localhost:6379/0

# Optional
LOG_LEVEL=INFO              # DEBUG | INFO | WARNING | ERROR
ENABLE_TELEGRAM=false       # true to enable Telegram notifications
TELEGRAM_BOT_TOKEN=your_token
```

---

## Compliance Modules

### Missouri Tax Calculator

```python
from src.compliance.missouri_tax import MissouriTaxCalculator
from decimal import Decimal
from datetime import datetime, timezone

calc = MissouriTaxCalculator()

# Calculate state tax (accounts for Aug 28, 2025 exemption)
capital_gain = Decimal('1000.00')
sale_date = datetime(2025, 9, 1, tzinfo=timezone.utc)

state_tax = calc.calculate_missouri_tax(capital_gain, sale_date)
# Returns Decimal('0.00') - 100% exempt after Aug 28, 2025
```

### Form 1099-DA Reconciliation

```python
from src.compliance.form_1099_da import Form1099DAReconciler, Form1099DA
from decimal import Decimal

reconciler = Form1099DAReconciler()

# Create 1099-DA from exchange
form = Form1099DA(
    payer_name="Binance.US",
    payer_tin="XX-XXXXXXX",
    gross_proceeds=Decimal('10000.00'),
    cost_basis=Decimal('9500.00'),
    tax_year=2026
)

# Reconcile against CARBS records
report = await reconciler.reconcile_exchange(form, 2026, 'binance')

if report.discrepancies:
    for disc in report.discrepancies:
        print(f"{disc.field}: Exchange ${disc.exchange_value}, "
              f"CARBS ${disc.carbs_value}, Diff ${disc.difference}")
```

---

## Additional Resources

- [Production Deployment Guide](PRODUCTION_DEPLOYMENT_GUIDE.md) - Full deployment instructions
- [Regulatory Updates 2025](REGULATORY_UPDATES_2025.md) - Latest regulatory changes
- [Exchange ToS Compliance](EXCHANGE_TOS_COMPLIANCE_ANALYSIS.md) - Terms of Service analysis
- [User Responsibilities](USER_RESPONSIBILITIES.md) - What you must do vs what CARBS does
- [Go-Live Checklist](../GO_LIVE_CHECKLIST.md) - Pre-production verification

---

## Contributing

When contributing to CARBS:

1. **Always use timezone-aware datetimes**
2. **Always use Decimal for money**
3. **Always use async for I/O operations**
4. **Always add type hints**
5. **Always write tests** (aim for >80% coverage)
6. **Always use structured logging**
7. **Never commit API keys** (use `.env`)
8. **Never use floats for money** (use Decimal)

---

## Getting Help

- Check existing tests for examples: `tests/test_*.py`
- Review compliance modules: `src/compliance/`
- Read exchange implementations: `src/exchanges/`
- Consult production guides: `docs/PRODUCTION_DEPLOYMENT_GUIDE.md`

---

**Last Updated:** 2025-12-19
