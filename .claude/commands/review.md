# /review — Code Review Checklist

Perform a comprehensive review of the current changes or specified file.

## Instructions

Review the provided code diff or file against these CARBS-specific criteria:

### Security Checks
- [ ] No API keys, secrets, or credentials in source files
- [ ] All external input validated with pydantic v2 models
- [ ] SSL verification enabled on all exchange connections
- [ ] Fernet encryption used for any credential storage
- [ ] No `shell=True` in subprocess calls
- [ ] No SQL string interpolation (use parameterized queries with asyncpg)

### Trading Safety
- [ ] Trading mode defaults to `paper` — no autonomous `live` activation
- [ ] Circuit breaker wraps all exchange API calls
- [ ] Kelly Criterion position sizing enforced for any live trade logic
- [ ] Risk limits respected (max_position_usd from config)

### Code Quality
- [ ] Type annotations present on all public functions
- [ ] `structlog` used instead of `print()` in src/
- [ ] Async functions used for all I/O operations
- [ ] No blocking calls inside `async def` (no `time.sleep`, use `asyncio.sleep`)
- [ ] Black line-length (120) respected
- [ ] No hardcoded exchange symbols (use `config.symbols`)

### Architecture
- [ ] Changes consistent with module's stated purpose
- [ ] No circular imports introduced
- [ ] Redis TTL for orderbook cache remains at 1 second
- [ ] Health endpoints remain functional if API layer modified

### Tests
- [ ] New functionality has corresponding test coverage
- [ ] Tests mock exchanges — no live API calls
- [ ] `pytest tests/ -v --cov=src` passes with ≥50% coverage

## Output Format
Report findings as:
- **PASS**: No issues found
- **WARN**: Minor issues (style, documentation)
- **FAIL**: Blocking issues (security, safety, test failures)

Provide specific file:line references for all findings.
