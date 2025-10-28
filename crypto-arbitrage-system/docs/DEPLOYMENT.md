# Deployment Guide

## DigitalOcean VPS Setup

### 1. Create Droplet
```bash
# Basic droplet: $12/month, 2GB RAM, 2 vCPUs
# Region: Tokyo (closest to Binance servers)
# OS: Ubuntu 24.04 LTS
```

### 2. Initial Setup
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

### 3. Deploy Application
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

### 4. Process Management (systemd)
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

### 5. Monitoring
```bash
# View logs
journalctl -u arbitrage -f

# Check metrics
curl http://localhost:8000/metrics

# Access Grafana
# Navigate to http://your-ip:3000
```

## Production Checklist

- [ ] Change default passwords in `.env`
- [ ] Enable firewall (UFW)
- [ ] Setup SSL/TLS for Grafana
- [ ] Configure backup strategy
- [ ] Test alerting system
- [ ] Monitor resource usage
- [ ] Set up log rotation
