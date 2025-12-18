# User Responsibilities for Exchange Compliance

**IMPORTANT:** CARBS is a software tool that helps you trade cryptocurrency. However, **YOU** are ultimately responsible for complying with all exchange Terms of Service, applicable laws, and regulations.

---

## ⚠️ What CARBS Can Do

CARBS provides:
- ✅ Rate limit enforcement (prevents API violations)
- ✅ Secure API key storage (encrypted in memory)
- ✅ Legitimate trading patterns (no wash trading, spoofing, or manipulation)
- ✅ Transaction record-keeping (7 years for tax compliance)
- ✅ Tax reporting tools (Form 8949, Missouri forms, 1099-DA reconciliation)

---

## ⚠️ What CARBS Cannot Do

CARBS **CANNOT:**
- ❌ Verify your identity (KYC) with exchanges
- ❌ Ensure you meet geographic restrictions
- ❌ Monitor your exchange account standing
- ❌ Accept Terms of Service on your behalf
- ❌ Guarantee your compliance with exchange policies
- ❌ Protect you from regulatory enforcement
- ❌ Monitor changes to exchange Terms of Service

---

## Your Critical Responsibilities

### 1. Account Setup and Verification

**YOU MUST:**

- [ ] **Create accounts** on supported exchanges (Binance, MEXC)
- [ ] **Complete KYC verification** on all exchanges
  - Government-issued photo ID required
  - Proof of address may be required
  - Selfie verification (liveness check)
- [ ] **Enable 2FA (Two-Factor Authentication)** on ALL exchange accounts
  - Use authenticator app (Google Authenticator, Authy)
  - DO NOT use SMS 2FA (less secure)
- [ ] **Set up API keys** with correct permissions:
  - ✅ Enable: "Trading" or "Spot Trading"
  - ❌ Disable: "Withdrawals" (for security)
  - ✅ Enable: IP whitelist if possible
- [ ] **Store API credentials securely** in `.env` file:
  ```bash
  # Never commit this file to git!
  BINANCE_API_KEY=your_key_here
  BINANCE_API_SECRET=your_secret_here
  MEXC_API_KEY=your_key_here
  MEXC_API_SECRET=your_secret_here
  ```

**Why this matters:**
- Exchanges REQUIRE KYC for API trading
- Without proper setup, you cannot trade
- Improper API permissions = security risk

---

### 2. Geographic Restrictions

**YOU MUST:**

- [ ] **Verify you can legally use each exchange** in your jurisdiction
- [ ] **Review geographic restrictions** in `docs/EXCHANGE_COMPLIANCE.md`
- [ ] **NEVER use KuCoin if you are a US person** (CFTC/FinCEN enforcement)
- [ ] **Set USER_JURISDICTION environment variable** if you are in the US:
  ```bash
  # In your .env file:
  USER_JURISDICTION=US
  ```
  This prevents accidental KuCoin usage (regulatory violation)

**Geographic Restrictions Summary:**

| Exchange | Restricted Locations |
|----------|---------------------|
| **Binance.com** | United States (use Binance.US instead) |
| **Binance.US** | NY, TX, VT, HI (check current list) |
| **MEXC** | US, Canada, Cuba, Crimea, Iran, Syria, North Korea |
| **KuCoin** | ⚠️ **US, Canada, mainland China** + active enforcement |

**If you violate geographic restrictions:**
- Your account will be suspended
- Funds may be frozen
- You may face legal consequences
- CARBS cannot help you recover funds

---

### 3. Reading and Accepting Terms of Service

**YOU MUST:**

- [ ] **Read EACH exchange's Terms of Service** BEFORE using CARBS:
  - Binance: https://www.binance.com/en/terms
  - Binance API: https://www.binance.com/en/terms-api
  - MEXC: https://www.mexc.com/user-agreement
  - KuCoin: https://www.kucoin.com/agreement (⚠️ US persons prohibited)

- [ ] **Accept the Terms of Service** on each exchange website
  - CARBS does NOT accept ToS on your behalf
  - You must click "I Accept" yourself

- [ ] **Review prohibited activities** (see below)

- [ ] **Understand you can be banned** for ToS violations

**Why this matters:**
- Exchanges can suspend your account for ToS violations
- "I didn't know" is not a valid excuse
- You could lose access to funds

---

### 4. Prohibited Trading Activities

**YOU MUST NOT:**

- ❌ **Wash Trading:** Trading with yourself to fake volume (CARBS doesn't do this - we trade across different exchanges)
- ❌ **Spoofing:** Placing orders you intend to cancel to manipulate price
- ❌ **Layering:** Multiple fake orders to create artificial depth
- ❌ **Market Manipulation:** Coordinated activity to move prices
- ❌ **Front-Running:** Trading ahead of large orders you're aware of
- ❌ **Using multiple accounts** to circumvent limits
- ❌ **Sharing API keys** with others
- ❌ **Commercial use** without exchange approval (personal trading is fine)

**CARBS's trading behavior:**
- ✅ Legitimate arbitrage (buy on Exchange A, sell on Exchange B)
- ✅ Small position sizes ($500 max default)
- ✅ Low frequency (20 trades/day max default)
- ✅ All orders intended to execute (not spoofing)
- ✅ Improves market efficiency (beneficial activity)

**Your responsibility:**
- Don't modify CARBS to engage in prohibited activities
- Don't coordinate with other traders
- Don't try to manipulate markets
- Trade honestly and transparently

---

### 5. Ongoing Compliance Maintenance

**YOU MUST:**

- [ ] **Maintain valid KYC status** on all exchanges
  - Update if your address changes
  - Renew verification if it expires
  - Respond to exchange requests promptly

- [ ] **Rotate API keys quarterly** (every 90 days)
  - Generate new keys
  - Update `.env` file
  - Delete old keys from exchange
  - See `docs/COMPLIANCE_MAINTENANCE.md`

- [ ] **Monitor exchange announcements** for policy changes
  - Subscribe to exchange newsletters
  - Check announcement pages monthly
  - Review `docs/EXCHANGE_COMPLIANCE.md` quarterly

- [ ] **Review Terms of Service quarterly** (Jan, Apr, Jul, Oct)
  - Check "Last Updated" date on ToS pages
  - Note any material changes
  - Update your practices if needed

- [ ] **Keep CARBS software updated**
  - Pull latest updates from repository
  - Review release notes for compliance changes
  - Test after updates

**Quarterly Checklist:** See `docs/COMPLIANCE_MAINTENANCE.md` for full schedule

---

### 6. Tax Compliance

**YOU MUST:**

- [ ] **Report ALL cryptocurrency trading income** to IRS
  - Even if you don't receive a 1099 form
  - Even small trades must be reported
  - Failure to report = tax evasion (felony)

- [ ] **File federal taxes** by April 15 each year
  - Use CARBS export: `python scripts/export_missouri_tax.py --year 2025`
  - Generate Form 8949 and Schedule D
  - Provide to tax preparer or file yourself

- [ ] **File Missouri state taxes** (if MO resident)
  - Note: Capital gains 100% exempt after Aug 28, 2025
  - Still must report, even if exempt
  - Use CARBS Missouri tax export

- [ ] **Starting 2026: Reconcile Form 1099-DA** from exchanges
  - Exchanges will send by Jan 31
  - Use CARBS reconciliation module (see `src/compliance/form_1099_da.py`)
  - Resolve any discrepancies before filing

- [ ] **Keep records for 7 years**
  - CARBS stores in database automatically
  - Export annually and keep backups
  - IRS can audit back 7 years (indefinitely if fraud suspected)

**Tax Resources:**
- IRS Cryptocurrency: https://www.irs.gov/businesses/small-businesses-self-employed/virtual-currencies
- Missouri DOR: https://dor.mo.gov/taxation/
- See `docs/MISSOURI_TAX_GUIDE.md` for full Missouri guidance

---

### 7. Security Responsibilities

**YOU MUST:**

- [ ] **Secure your API keys**
  - Never share with anyone
  - Never commit `.env` to git
  - Use `.gitignore` to exclude `.env`
  - Store backups in password manager (encrypted)

- [ ] **Use strong passwords** on exchanges
  - Minimum 16 characters
  - Unique for each exchange
  - Use password manager (1Password, Bitwarden, LastPass)

- [ ] **Enable 2FA** on everything
  - Exchange accounts
  - Email account
  - Password manager
  - GitHub (if contributing)

- [ ] **Monitor for suspicious activity**
  - Check exchange login history
  - Review API key activity logs
  - Set up exchange security alerts
  - Disable API keys if compromised

- [ ] **Secure your computer**
  - Keep OS updated
  - Use antivirus/antimalware
  - Don't run CARBS on public Wi-Fi (use VPN)
  - Encrypt your hard drive

**If your API keys are compromised:**
1. **Immediately delete keys** from exchange
2. **Check for unauthorized trades**
3. **Change exchange password**
4. **Review account balances**
5. **Contact exchange support**
6. **Generate new API keys** (after securing your system)

---

### 8. Account Standing and Compliance Notifications

**YOU MUST:**

- [ ] **Respond promptly** to exchange compliance emails
  - KYC verification requests
  - Suspicious activity inquiries
  - Account restrictions or warnings
  - Policy violation notices

- [ ] **Monitor account standing**
  - Log into each exchange weekly
  - Check for notifications or warnings
  - Verify no restrictions on account
  - Ensure trading permissions active

- [ ] **Stop trading immediately** if:
  - Account is restricted or suspended
  - You receive a compliance warning
  - Exchange requests additional verification
  - You're unsure if your activity is compliant

- [ ] **Contact exchange support** for any issues
  - Don't ignore compliance requests
  - Document all communications
  - Follow their resolution process

**Warning signs of compliance issues:**
- Email from exchange compliance team
- Unable to place trades or withdraw funds
- API calls returning "account restricted" errors
- Login prompts for additional verification

**If your account is restricted:**
1. **Stop using CARBS** for that exchange
2. **Read the notification carefully**
3. **Follow exchange's instructions**
4. **Provide requested documents**
5. **Do NOT create a new account** (ToS violation)

---

### 9. Understanding Regulatory Risks

**YOU MUST:**

- [ ] **Understand cryptocurrency regulations** in your jurisdiction
  - Federal: IRS, SEC, CFTC, FinCEN
  - State: Missouri regulations (if MO resident)
  - Consult attorney if unsure

- [ ] **Monitor regulatory developments**
  - Subscribe to IRS cryptocurrency updates
  - Follow SEC/CFTC crypto enforcement
  - Check Missouri tax law changes
  - Review `docs/COMPLIANCE_AUDIT_REPORT.md`

- [ ] **Seek professional advice** when needed
  - CPA for tax questions
  - Attorney for legal/regulatory questions
  - Financial advisor for investment strategy

- [ ] **Document your compliance efforts**
  - Keep emails, forms, receipts
  - Export CARBS audit logs
  - Save ToS versions you agreed to
  - Maintain tax records for 7+ years

**As a personal trader, you are exempt from:**
- ✅ FinCEN Money Services Business (MSB) registration
- ✅ SEC broker-dealer registration
- ✅ CFTC futures commission merchant (FCM) registration

**But you MUST comply with:**
- ⚠️ IRS tax reporting (Form 8949, Schedule D, 1099-DA)
- ⚠️ State tax reporting (Missouri)
- ⚠️ Exchange Terms of Service
- ⚠️ Anti-money laundering laws (don't facilitate crime)

---

### 10. When You Need Help

**Questions about:**

**Exchange ToS:**
- Read: `docs/EXCHANGE_COMPLIANCE.md`
- Contact: Exchange support

**Tax Compliance:**
- Read: `docs/MISSOURI_TAX_GUIDE.md` (if MO resident)
- Read: `crypto-arbitrage-system/COMPLIANCE_AUDIT_REPORT.md`
- Contact: Licensed CPA specializing in cryptocurrency

**Regulatory Compliance:**
- Read: `crypto-arbitrage-system/COMPLIANCE_AUDIT_REPORT.md`
- Contact: Attorney specializing in cryptocurrency/securities law

**CARBS Technical Issues:**
- Read: `GETTING_STARTED.md`
- Read: `docs/RUNBOOK.md`
- GitHub Issues: (if open source)

**Account Suspension/Restriction:**
- Contact: Exchange support (Binance, MEXC, KuCoin)
- Document: Everything (emails, screenshots, dates)
- Consult: Attorney if large amounts at stake

---

## Certification and Acknowledgment

By using CARBS, you acknowledge and certify that:

- ✅ I have read and understood this document
- ✅ I have read and accepted each exchange's Terms of Service
- ✅ I am legally permitted to use each exchange in my jurisdiction
- ✅ I am NOT a US person attempting to use KuCoin
- ✅ I will comply with all tax reporting requirements
- ✅ I will maintain proper account verification (KYC, 2FA)
- ✅ I understand CARBS cannot ensure my compliance
- ✅ I accept full responsibility for regulatory compliance
- ✅ I will monitor my account standing and respond to compliance requests
- ✅ I will seek professional advice when needed

**Remember:** CARBS is a tool. Like any tool, it can be used correctly or incorrectly. **YOU** are responsible for using it correctly and legally.

---

## Quick Reference: Your Compliance Checklist

### Before First Use:
- [ ] Read this entire document
- [ ] Read and accept each exchange's Terms of Service
- [ ] Complete KYC on all exchanges
- [ ] Enable 2FA on all accounts
- [ ] Set up API keys with correct permissions
- [ ] Configure `.env` file with credentials
- [ ] If US person: Set `USER_JURISDICTION=US` in `.env`
- [ ] If US person: DO NOT enable KuCoin

### Daily (when trading):
- [ ] Check exchange announcements
- [ ] Monitor CARBS logs for errors
- [ ] Review trade activity

### Monthly (1st of month):
- [ ] Review exchange account standing
- [ ] Check for compliance notifications
- [ ] Export CARBS database backup

### Quarterly (Jan, Apr, Jul, Oct 15th):
- [ ] Review exchange Terms of Service for updates
- [ ] Rotate API keys (every 90 days)
- [ ] Run system health checks
- [ ] Export transaction history from exchanges

### Annually (January):
- [ ] Export tax data: `python scripts/export_missouri_tax.py --year 2025`
- [ ] Reconcile Form 1099-DA (starting 2026)
- [ ] File federal taxes by April 15
- [ ] File state taxes (if applicable)
- [ ] Update to latest CARBS version
- [ ] Review compliance documentation updates

**Full schedule:** See `docs/COMPLIANCE_MAINTENANCE.md`

---

## Legal Disclaimers

**This document is for informational purposes only and does not constitute legal or tax advice.**

- CARBS developers are NOT responsible for your compliance failures
- CARBS developers are NOT responsible for exchange ToS violations
- CARBS developers are NOT responsible for tax filing errors
- CARBS developers are NOT responsible for regulatory enforcement against you
- CARBS developers are NOT responsible for losses due to account suspension

**Consult licensed professionals:**
- **CPA** for tax questions
- **Attorney** for legal/regulatory questions
- **Exchange support** for account issues

**You use CARBS at your own risk.**

---

## Document Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-18 | Initial creation |

**Next Review Date:** 2026-01-15

**Questions?** See `docs/EXCHANGE_COMPLIANCE.md` for exchange-specific requirements or consult a professional.
