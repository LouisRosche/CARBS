# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |

---

## Reporting a Vulnerability

**DO NOT create a public GitHub issue for security vulnerabilities.**

1. Email security concerns to the project maintainers
2. Include: description, steps to reproduce, potential impact, suggested fixes (optional)

### Response Times

| Severity | Acknowledgment | Resolution |
|----------|---------------|------------|
| Critical | 48 hours | 24-72 hours |
| High | 48 hours | 1-2 weeks |
| Medium | 48 hours | 2-4 weeks |
| Low | 48 hours | Next release cycle |

### Severity Classification

| Severity | Description | Examples |
|----------|-------------|----------|
| Critical | System compromise, data breach | RCE, authentication bypass, credential exposure |
| High | Significant impact | Privilege escalation, sensitive data access |
| Medium | Limited impact | Information disclosure, limited access |
| Low | Minimal impact | Minor information leaks, hardening issues |

---

## API Key Setup

### Security Rules

1. **Never commit API keys to git** -- `.env` is gitignored
2. **Use environment variables only** -- never `config/config.yaml`
3. **Enable IP whitelisting** on all exchanges
4. **Restrict permissions** -- trade + read only, no withdrawals
5. **Rotate keys regularly**

### Binance

1. Log into Binance -> API Management
2. Create new API key
3. Enable "Enable Spot & Margin Trading"
4. **Disable** "Enable Withdrawals"
5. Add your server IP to whitelist
6. Copy key and secret to `.env`

### Coinbase

1. Log into Coinbase Pro -> API settings
2. Create API key with "Trade" permission only
3. Copy credentials to `.env`

### Kraken

1. Log into Kraken -> Settings -> API
2. Generate new key
3. Enable "Query Funds" and "Create & Modify Orders"
4. **Disable** "Withdraw Funds"
5. Copy to `.env`

### Master Encryption Key

```bash
# Generate master key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set in .env
CARBS_MASTER_KEY=<generated-key>

# Protect .env file
chmod 600 .env
```

---

## Built-in Security Features

| Feature | Description |
|---------|-------------|
| Fernet Encryption | All stored credentials encrypted via `src/utils/secure_credentials.py` |
| Rate Limiting | Protection against brute force and API abuse |
| Audit Logging | Comprehensive trail of all operations |
| Circuit Breaker | Automatic halt on exchange anomalies |
| Emergency Stop | One-click trading halt |
| Password Hashing | SHA-256 with TOTP-based 2FA support |
| Session Management | Expiration and failed login tracking |

### Data Protection

- Sensitive data encrypted at rest (Fernet)
- No plaintext credential storage
- Secure secret rotation support
- GDPR-compliant data handling

---

## Security Best Practices

### Network

- Always use HTTPS/WSS for exchange connections
- Configure firewall rules to limit exposure
- Use VPN for production deployments
- Never disable SSL verification in production

### Database

- Use strong, unique passwords
- Enable encryption at rest
- Limit network access to database
- Regular encrypted backups

### Access Control

- Enable 2FA for all admin and exchange accounts
- Review audit logs regularly
- Implement principle of least privilege
- Use IP whitelisting on all exchange APIs

### Trading Safety

- Set conservative position limits
- Enable daily loss limits
- Test in paper mode first (2+ weeks recommended)
- Monitor for unusual activity

---

## Deployment Security Checklist

- [ ] All API keys stored in `.env` (not in code or config.yaml)
- [ ] Master encryption key set (`CARBS_MASTER_KEY`)
- [ ] `.env` file permissions set (`chmod 600`)
- [ ] SSL certificates configured
- [ ] Database credentials secured
- [ ] Firewall rules configured
- [ ] 2FA enabled on all exchange accounts
- [ ] Audit logging enabled
- [ ] Emergency stop tested
- [ ] Backup encryption enabled
- [ ] Network segmentation in place
- [ ] IP whitelisting enabled on exchanges
- [ ] Withdrawal permissions disabled on API keys

---

## Compliance

CARBS includes features supporting:

- SOX 404 compliance framework
- GAAP financial reporting (ASC 606, 820, 825)
- Tax reporting (Form 8949, Schedule D, 1099-DA)
- AML/KYC integration hooks
- Audit trail requirements

See [COMPLIANCE.md](COMPLIANCE.md) for details.

---

For security-related inquiries, contact the project maintainers through appropriate channels.
