# Configuration Guide

## Configuration Sources

CARBS uses multiple configuration sources with the following precedence (highest to lowest):

1. **Environment Variables** (highest priority)
2. **`.env` file**
3. **`config/config.yaml`**
4. **Default values in code** (lowest priority)

## Precedence Rules

### Example: Database Host

```python
# Priority order:
db_host = os.getenv('DB_HOST')           # 1. Environment variable
       or load_from_dotenv('DB_HOST')    # 2. .env file
       or config_yaml['database']['host'] # 3. config.yaml
       or 'localhost'                     # 4. Default value
```

### When to Use Each

| Source | Use Case | Example |
|--------|----------|---------|
| **Environment Variables** | Production secrets, container orchestration | `DB_PASSWORD`, `API_KEYS` |
| **`.env` file** | Local development, secrets not in git | API keys, passwords |
| **`config.yaml`** | Application settings, non-secrets | Trading parameters, symbols |
| **Code defaults** | Fallback values | Timeouts, retry counts |

---

## Environment Variables

### Required

```bash
# Database
POSTGRES_DB=arbitrage
POSTGRES_USER=arbitrage_user
POSTGRES_PASSWORD=<your-password>
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=<your-password>

# Security
CARBS_MASTER_KEY=<generated-key>
```

### Optional

```bash
# Exchange API Keys (leave empty for paper trading)
BINANCE_API_KEY=
BINANCE_API_SECRET=
COINBASE_API_KEY=
COINBASE_API_SECRET=

# Notifications
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Application
LOG_LEVEL=INFO
PAPER_TRADING=true
ENVIRONMENT=development
```

---

## config.yaml Structure

```yaml
trading:
  mode: paper              # paper | live
  min_spread_percent: 0.3  # Minimum spread to consider
  max_spread_percent: 5.0  # Maximum spread (sanity check)
  max_position_usd: 500    # Maximum position size

exchanges:
  binance:
    enabled: true
    taker_fee: 0.001       # 0.1%
  coinbase:
    enabled: true
    taker_fee: 0.006       # 0.6%
  kraken:
    enabled: false
    taker_fee: 0.0016      # 0.16%

symbols:
  - BTC/USDT
  - ETH/USDT

risk:
  max_daily_loss_usd: 100
  max_drawdown_percent: 10
  kelly_fraction: 0.25     # Use 25% of Kelly Criterion

monitoring:
  prometheus_port: 9090
  grafana_port: 3000
```

---

## Common Configurations

### Development Setup

```bash
# .env
ENVIRONMENT=development
LOG_LEVEL=DEBUG
PAPER_TRADING=true
```

```yaml
# config.yaml
trading:
  mode: paper
  max_position_usd: 100
```

### Production Setup

```bash
# .env (from secrets manager)
ENVIRONMENT=production
LOG_LEVEL=INFO
PAPER_TRADING=false
CARBS_MASTER_KEY=<from-vault>
```

```yaml
# config.yaml
trading:
  mode: live
  max_position_usd: 500
  min_spread_percent: 0.5  # Higher threshold for production
```

---

## Secrets Management

### DO NOT commit secrets to git

```bash
# .gitignore already includes:
.env
*.key
*.pem
credentials.json
```

### Generate Master Key

```bash
# Generate secure master key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Store in environment variable
export CARBS_MASTER_KEY=<generated-key>
```

### Protect .env file

```bash
chmod 600 .env
```

---

## Configuration Validation

On startup, CARBS validates:

✅ **Required variables set**
✅ **Numeric ranges valid** (e.g., spread > 0)
✅ **API keys format correct** (if provided)
✅ **Exchange names valid**
✅ **Symbol format correct** (BASE/QUOTE)

**If validation fails:** Application will not start and will log specific error.

---

## Troubleshooting

### Issue: Config not loading

```bash
# Check file exists
ls -la config/config.yaml

# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"
```

### Issue: Environment variables not picked up

```bash
# Check .env file loaded
cat .env | grep -v "^#" | grep -v "^$"

# Check environment
env | grep CARBS
env | grep POSTGRES
```

### Issue: Trading mode not changing

```bash
# Config cached? Restart application
docker compose restart

# Check config file
grep "mode:" config/config.yaml

# Check for environment override
env | grep TRADING_MODE
```

---

## Best Practices

1. **Never commit `.env`** - Use `.env.example` as template
2. **Use environment variables for secrets** - Not config.yaml
3. **Document all config options** - Update this file when adding new options
4. **Validate on startup** - Fail fast if misconfigured
5. **Log configuration loaded** - At INFO level (without secrets)

---

**Last Updated:** 2025-12-17
