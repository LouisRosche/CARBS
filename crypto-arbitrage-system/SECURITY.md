# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

1. **DO NOT** create a public GitHub issue for security vulnerabilities
2. Email security concerns to the project maintainers
3. Include the following information:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

### What to Expect

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 7 days
- **Resolution Timeline**: Depends on severity
  - Critical: 24-72 hours
  - High: 1-2 weeks
  - Medium: 2-4 weeks
  - Low: Next release cycle

### Severity Classification

| Severity | Description | Examples |
|----------|-------------|----------|
| Critical | System compromise, data breach | RCE, authentication bypass, credential exposure |
| High | Significant impact | Privilege escalation, sensitive data access |
| Medium | Limited impact | Information disclosure, limited access |
| Low | Minimal impact | Minor information leaks, hardening issues |

## Security Best Practices

### API Credentials

- **Never** commit API keys or secrets to version control
- Use environment variables or encrypted storage
- The `.env` file should **never** be committed (check `.gitignore`)
- Rotate API keys regularly
- Use read-only API keys when possible

### Configuration

```bash
# Set master encryption key securely
export CARBS_MASTER_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# Protect .env file
chmod 600 .env
```

### Access Control

- Use role-based access control (RBAC)
- Enable 2FA for all admin accounts
- Review audit logs regularly
- Implement principle of least privilege

### Network Security

- Always use HTTPS/WSS for exchange connections
- Configure firewall rules to limit exposure
- Use VPN for production deployments
- Enable SSL verification (never disable in production)

### Database Security

- Use strong, unique passwords
- Enable encryption at rest
- Limit network access to database
- Regular backups with encryption

## Security Features

### Built-in Protections

- **Encryption**: Fernet encryption for stored credentials
- **Rate Limiting**: Protection against brute force attacks
- **Audit Logging**: Comprehensive trail of all operations
- **Circuit Breaker**: Automatic halt on anomalies
- **Emergency Stop**: One-click trading halt

### Authentication

- Password hashing with SHA-256
- TOTP-based 2FA support
- Session management with expiration
- Failed login attempt tracking

### Data Protection

- Sensitive data encrypted at rest
- No plaintext credential storage
- Secure secret rotation support
- GDPR-compliant data handling

## Security Checklist for Deployment

- [ ] All API keys stored securely (not in code)
- [ ] Master encryption key set via environment
- [ ] SSL certificates configured
- [ ] Database credentials secured
- [ ] Firewall rules configured
- [ ] 2FA enabled for all admin accounts
- [ ] Audit logging enabled
- [ ] Emergency stop tested
- [ ] Backup encryption enabled
- [ ] Network segmentation in place

## Known Security Considerations

### Exchange API Keys

- Grant minimum required permissions
- Use IP whitelisting when available
- Set withdrawal restrictions
- Monitor for unauthorized access

### Trading Risks

- Set conservative position limits
- Enable daily loss limits
- Test in paper mode first
- Monitor for unusual activity

## Compliance

CARBS includes features to support:

- SOX 404 compliance framework
- GAAP financial reporting
- Tax reporting (Form 8949, 1099-B)
- AML/KYC integration hooks
- Audit trail requirements

## Contact

For security-related inquiries, please contact the project maintainers through appropriate channels.
