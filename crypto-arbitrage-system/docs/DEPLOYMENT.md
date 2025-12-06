# CARBS Local-First Deployment Guide

This guide covers deploying CARBS (Crypto ARBitrage System) with a local-first approach that maximizes control while ensuring 24/7 operation.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LOCAL MACHINE (Primary)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │   CARBS     │  │   Redis     │  │  PostgreSQL │  │  Dashboard  │ │
│  │   Engine    │  │   Cache     │  │   Database  │  │   (Rich)    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
│         │                │                │                │         │
│         └────────────────┴────────────────┴────────────────┘         │
│                                   │                                   │
│                           ┌───────┴───────┐                          │
│                           │  Telegram Bot │                          │
│                           │   (Alerts)    │                          │
│                           └───────────────┘                          │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                              ▼
            ┌───────────────┐              ┌───────────────┐
            │    Binance    │              │   Coinbase    │
            │   Kraken      │              │    KuCoin     │
            │   (Exchanges) │              │   (Exchanges) │
            └───────────────┘              └───────────────┘
```

## Deployment Options

### Option 1: Pure Local (Recommended for Starting)

**Pros:**
- Complete control over your data and keys
- No monthly hosting costs
- Data stays on your machine
- Fastest execution (no network latency)

**Cons:**
- Stops when computer is off
- Requires always-on machine

**Best for:** Testing, paper trading, learning the system

### Option 2: Local + Lightweight VPS Fallback

**Pros:**
- Local control with 24/7 backup
- VPS only activates when local is offline
- Low cost (~$5-10/month)

**Cons:**
- More complex setup
- Need to manage two environments

**Best for:** Live trading with reliability needs

### Option 3: Dedicated Mini Server (Raspberry Pi / Intel NUC)

**Pros:**
- Always on, low power (~5-15W)
- Complete control
- One-time cost ($100-300)
- Runs silently

**Cons:**
- Less powerful than desktop
- Need to set up and maintain

**Best for:** Serious local-first operation

---

## Option 1: Pure Local Setup

### Prerequisites

```bash
# System Requirements
- Python 3.11+
- 8GB RAM minimum (16GB recommended)
- 50GB disk space
- Stable internet connection
```

### Step 1: Install Dependencies

```bash
# Clone repository
git clone <your-repo> carbs
cd carbs

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Install Local Services

#### PostgreSQL
```bash
# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql

# Create database
sudo -u postgres createdb carbs
sudo -u postgres createuser carbs_user -P

# Mac (using Homebrew)
brew install postgresql
brew services start postgresql
createdb carbs
```

#### Redis
```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis

# Mac
brew install redis
brew services start redis
```

### Step 3: Configure Environment

```bash
# Create .env file
cp .env.example .env

# Edit .env with your settings
nano .env
```

**.env contents:**
```bash
# Master encryption key (generate once, save securely!)
CARBS_MASTER_KEY=your_generated_key_here

# Database
DATABASE_URL=postgresql://carbs_user:password@localhost:5432/carbs

# Redis
REDIS_URL=redis://localhost:6379/0

# Telegram alerts
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Trading mode (paper/live)
TRADING_MODE=paper
```

### Step 4: Initial Setup

```bash
# Run setup wizard
python -m src.cli.commands setup

# This will:
# 1. Create data directories
# 2. Generate encryption key (if not set)
# 3. Create admin user
# 4. Set up 2FA
```

### Step 5: Add Exchange Credentials

```bash
# Add exchange API keys (stored encrypted)
python -m src.cli.commands creds add binance
python -m src.cli.commands creds add coinbase

# List configured exchanges
python -m src.cli.commands creds list
```

### Step 6: Start Trading

```bash
# Start in paper mode (recommended first!)
python -m src.cli.commands start --mode paper

# Or launch dashboard
python -m src.cli.commands dashboard
```

---

## Option 2: Local + VPS Fallback

This setup runs primarily on your local machine but fails over to a VPS when your machine is offline.

### VPS Requirements

- $5-10/month VPS (DigitalOcean, Linode, Vultr)
- 1GB RAM, 1 CPU minimum
- Ubuntu 22.04 LTS

### Local Setup

Follow Option 1 steps, then add heartbeat monitoring:

```python
# Add to your config
HEARTBEAT_INTERVAL=60  # seconds
VPS_FAILOVER_URL=https://your-vps-ip:8443/api/heartbeat
```

### VPS Setup

```bash
# On VPS: Install same dependencies
ssh user@your-vps-ip
git clone <your-repo> carbs
cd carbs

# Install and configure same as local
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure as STANDBY mode
echo "OPERATION_MODE=standby" >> .env
```

### Failover Logic

The VPS runs in standby mode:
1. Receives heartbeat from local every 60 seconds
2. If 3 heartbeats missed (3 minutes), activates trading
3. When local comes back online, VPS returns to standby
4. All trades sync via shared database (optional) or Telegram alerts

---

## Option 3: Dedicated Mini Server

### Recommended Hardware

**Budget Option: Raspberry Pi 4 (8GB)**
- Cost: ~$75-100
- Power: 5W
- Good for: Paper trading, monitoring

**Better Option: Intel NUC or Mini PC**
- Cost: ~$200-400
- Power: 10-15W
- Good for: Live trading, faster execution

### Docker Compose Setup

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  carbs:
    build: .
    environment:
      - CARBS_MASTER_KEY=${CARBS_MASTER_KEY}
      - DATABASE_URL=postgresql://carbs:carbs@postgres:5432/carbs
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=carbs
      - POSTGRES_PASSWORD=carbs
      - POSTGRES_DB=carbs
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

```bash
# Start everything
docker-compose up -d

# View logs
docker-compose logs -f carbs
```

---

## VPS Deployment (Cloud Option)

If you prefer cloud deployment:

### DigitalOcean VPS Setup

#### 1. Create Droplet
```bash
# Basic droplet: $12/month, 2GB RAM, 2 vCPUs
# Region: Choose closest to your target exchanges
# OS: Ubuntu 24.04 LTS
```

#### 2. Initial Setup
```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker

# Install Docker Compose
apt install docker-compose-plugin -y

# Install Python 3.11
apt install python3.11 python3.11-venv -y
```

#### 3. Deploy Application
```bash
# Clone repository
git clone https://github.com/yourusername/crypto-arbitrage-system.git
cd crypto-arbitrage-system

# Setup environment
make setup
nano .env  # Edit with your credentials

# Start infrastructure
make start

# Initialize database
make db-init

# Run application
make run
```

#### 4. Process Management (systemd)
```bash
# Create service file
cat > /etc/systemd/system/arbitrage.service << 'EOFSVC'
[Unit]
Description=Crypto Arbitrage System
After=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/crypto-arbitrage-system
ExecStart=/root/crypto-arbitrage-system/venv/bin/python src/main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOFSVC

# Enable and start
systemctl enable arbitrage
systemctl start arbitrage
systemctl status arbitrage
```

---

## Security Hardening

### 1. Firewall Configuration

```bash
# Ubuntu/Debian with UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (change port for security)
sudo ufw allow 22/tcp

sudo ufw enable
```

### 2. Exchange IP Whitelisting

For each exchange, add your server's IP to the API key whitelist:

**Binance:**
1. Log in to Binance
2. Go to API Management
3. Edit your API key
4. Add your IP under "Restrict access to trusted IPs only"

**Do this for all exchanges before going live.**

### 3. API Key Best Practices

```
DO:
- Use trade-only keys (no withdrawal permissions)
- Enable IP whitelisting on all exchanges
- Store keys encrypted (CARBS does this automatically)
- Rotate keys every 90 days

DON'T:
- Enable withdrawal permissions for trading keys
- Share API keys or master key
- Store keys in plain text
- Use same key for multiple bots
```

### 4. Hardware Key (YubiKey) Setup

```bash
# Install YubiKey tools
sudo apt install yubikey-manager

# Register hardware key with CARBS
python -m src.cli.commands security setup-yubikey
```

### 5. Backup Strategy

```bash
# What to backup:
# 1. .env file (contains master key)
# 2. data/ directory (encrypted secrets, audit logs)
# 3. config/ directory (settings)

# Create encrypted backup
tar -czvf carbs_backup_$(date +%Y%m%d).tar.gz .env data/ config/
gpg -c carbs_backup_$(date +%Y%m%d).tar.gz

# Store backup in multiple locations:
# - External drive
# - Cloud storage (encrypted)
# - Safety deposit box (for master key)
```

---

## Monitoring When Computer is Off

### Telegram Alerts (Primary)

All critical events are sent to Telegram:
- Trade executions with P&L
- Emergency stops
- System errors
- Daily summaries

### Health Monitoring

```bash
# View logs
journalctl -u arbitrage -f

# Check metrics
curl http://localhost:8000/metrics

# Access Grafana (if configured)
# Navigate to http://your-ip:3000
```

---

## Cost Comparison

| Setup | Monthly Cost | Power Cost | Total |
|-------|-------------|------------|-------|
| Local Only | $0 | ~$5-10 | $5-10 |
| Local + VPS | $5-10 | ~$5-10 | $10-20 |
| Mini Server | $0 | ~$2-3 | $2-3 |
| Cloud Only | $12-50 | $0 | $12-50 |

---

## Quick Start Checklist

- [ ] Install Python 3.11+
- [ ] Install PostgreSQL and Redis
- [ ] Clone repository
- [ ] Create virtual environment
- [ ] Install dependencies
- [ ] Run setup wizard
- [ ] Configure .env file
- [ ] Add exchange credentials
- [ ] Enable 2FA and/or hardware key
- [ ] Add exchange IP whitelists
- [ ] Test with paper trading
- [ ] Set up Telegram alerts
- [ ] Create backup of master key
- [ ] Start trading!

## Production Checklist

- [ ] Change default passwords in `.env`
- [ ] Enable firewall (UFW)
- [ ] Setup SSL/TLS for any web interfaces
- [ ] Configure backup strategy
- [ ] Test alerting system
- [ ] Monitor resource usage
- [ ] Set up log rotation

---

## Troubleshooting

### "Cannot connect to database"
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check connection
psql -U carbs_user -d carbs -h localhost
```

### "Redis connection refused"
```bash
# Check Redis is running
sudo systemctl status redis

# Test connection
redis-cli ping
```

### "API key rejected"
1. Verify key is correct
2. Check IP whitelist includes your current IP
3. Verify key has required permissions
4. Check key hasn't expired

### "Trade execution failed"
1. Check exchange status page
2. Verify sufficient balance
3. Check network connectivity
4. Review audit logs: `python -m src.cli.commands audit`
