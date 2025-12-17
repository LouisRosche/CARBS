# Changelog

All notable changes to CARBS (Crypto ARBitrage System) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GitHub Actions CI/CD workflow with lint, type-check, test, and security jobs
- Dockerfile for application containerization
- Pre-commit configuration for code quality enforcement
- pyproject.toml for modern Python packaging
- Comprehensive test suites for compliance, ML, signals, and web modules
- conftest.py with shared pytest fixtures
- CHANGELOG.md for tracking changes
- SECURITY.md with security policy and vulnerability reporting

### Changed
- Replaced bare except clauses with specific Exception handling in gaap_financial_statements.py
- Converted print statements to logging in non-CLI modules

### Fixed
- 9 bare except clauses that could mask critical exceptions

## [1.0.0] - 2024-01-15

### Added
- Initial release of CARBS
- Multi-exchange arbitrage detection (Binance, Coinbase, Kraken, KuCoin, MEXC)
- Real-time WebSocket order book streaming
- ML-based 6-factor opportunity scoring
- Triangle arbitrage detection
- Circuit breaker pattern for fault tolerance
- Kelly Criterion position sizing
- Risk management (VaR, Sharpe/Sortino ratios)
- GAAP-compliant financial reporting
- Tax lot tracking (FIFO, LIFO, HIFO)
- Encrypted credential storage
- Role-based access control
- Comprehensive audit logging
- CLI dashboard with Rich terminal UI
- REST API with FastAPI
- Prometheus metrics and Grafana dashboards
- Docker Compose infrastructure (PostgreSQL, TimescaleDB, Redis)
- Kubernetes-ready health probes

### Security
- Fernet encryption for API credentials
- Rate limiting with LRU eviction
- SSL/TLS verification on all connections
- JWT token authentication
- 2FA support with TOTP
- Audit trail for all operations
