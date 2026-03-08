# /test-tdd — Test-Driven Development Workflow

Enforce strict TDD protocol for new feature implementation.

## Instructions

Follow this exact TDD sequence for the specified feature or bug fix:

### Phase 1: Write a Failing Test
1. Identify the single behavior to test
2. Write **exactly one test** with **one assertion**
3. Verify the test fails for the RIGHT reason:
   - MUST fail due to missing business logic
   - Must NOT fail due to syntax errors, missing imports, or undefined properties
4. Run: `cd crypto-arbitrage-system && pytest tests/ -k "<test_name>" -v`
5. Confirm failure output shows expected vs actual mismatch

### Phase 2: Implement Minimum Code
1. Write the **absolute minimum** code to make the test pass
2. Do NOT add:
   - Extra methods not required by the test
   - Future-proofing logic
   - Speculative properties or configurations
   - Documentation beyond type hints
3. Run test again — it must now pass

### Phase 3: Verify No Regressions
1. Run full suite: `pytest tests/ -v --cov=src`
2. Confirm all previously passing tests still pass
3. Coverage must remain ≥50%

### Phase 4: Refactor (Optional)
Only if code quality is clearly poor:
1. Refactor WITHOUT changing behavior
2. Re-run tests after each refactor step
3. Stop when tests pass and code is readable

## Constraints
- Maximum 5 TDD iterations before requesting human review
- Never generate a full test suite in one step
- Test file naming: `tests/test_<module_name>.py`
- Use `pytest-asyncio` for async functions
- Mock all external dependencies (exchanges, DB, Redis)

## CARBS-Specific Test Patterns
```python
# Always mock exchange connections
@pytest.fixture
def mock_exchange(mocker):
    return mocker.patch("src.exchanges.binance.BinanceAdapter")

# Async test pattern
@pytest.mark.asyncio
async def test_arbitrage_detection(mock_exchange):
    # Arrange
    mock_exchange.get_ticker.return_value = {"bid": 100.0, "ask": 100.5}

    # Act
    result = await detect_arbitrage(mock_exchange, "BTC/USDT")

    # Assert (one assertion)
    assert result.spread_percent > 0
```
