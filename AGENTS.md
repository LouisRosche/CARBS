# AGENTS.md — CARBS AI Agent Standards

Cross-platform agent configuration for Cursor, Copilot, Windsurf, Claude Code, and Codex.

## Project Context
**CARBS** is a Python 3.11+ cryptocurrency arbitrage detection and execution platform.
Default mode: paper trading. Live trading is an explicit opt-in requiring human approval.

## Setup Commands
```bash
cd crypto-arbitrage-system
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Fill in API keys — never commit .env
docker compose up -d   # Start postgres, redis, prometheus
python scripts/init_db.py
```

## Code Style Rules
- Language: Python 3.11+, fully typed (PEP 484)
- Formatter: `black --line-length 120`
- Import order: `isort --profile black`
- Linter: `flake8` (max-line-length 120) + `mypy --strict` for src/
- No `print()` in src/ — use `structlog` exclusively
- All public functions require type annotations

## Testing Protocol
```bash
cd crypto-arbitrage-system
pytest tests/ -v --cov=src --cov-fail-under=50
```
- Framework: pytest + pytest-asyncio (`asyncio_mode = "auto"`)
- Always mock exchange connections — never hit live APIs in tests
- One assertion per test case preferred
- Integration tests take precedence over unit tests (Testing Trophy model)

## Commit Guidelines
- Format: `<type>(<scope>): <short description>`
- Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
- Example: `fix(exchanges): handle ccxt NetworkError on reconnect`
- Never commit: `.env`, API keys, secrets, live trade configurations
- Pre-commit hooks enforced via `.pre-commit-config.yaml`

## Security Constraints
- API keys encrypted with Fernet via `src/utils/credentials.py`
- SSL verification mandatory on all exchange connections
- No shell=True in subprocess calls
- Input validation via pydantic v2 at all system boundaries
- Run `bandit -r src/` before any security-sensitive PR

## Architecture Rules
1. Circuit breaker wraps ALL exchange API calls — never bypass
2. `mode: paper` is default in `config/config.yaml` — live requires explicit human approval
3. Redis orderbook cache TTL = 1 second (do not increase)
4. Async-first: all I/O operations must use `async def`
5. Kelly Criterion sizing is mandatory for any live position

## Agent Behavior
- Plan before executing: propose file changes and get implicit approval via test passing
- Limit autonomous changes to files within `crypto-arbitrage-system/`
- Do not modify `config/config.yaml` trading mode to `live` autonomously
- Run `make lint` and `make test` after every code modification
- If tests fail after 3 attempts, halt and report the error
