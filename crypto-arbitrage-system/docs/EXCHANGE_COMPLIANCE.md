# Exchange Compliance Guide

**Last Updated:** 2025-12-18
**Review Schedule:** Quarterly (Jan, Apr, Jul, Oct)

## Overview

This document outlines the Terms of Service (ToS) and compliance requirements for each cryptocurrency exchange supported by CARBS. As a personal trader, you are responsible for ensuring your trading activities comply with each exchange's policies.

## ⚠️ Critical Disclaimer

**YOU ARE RESPONSIBLE FOR:**
- Reading and accepting each exchange's Terms of Service
- Complying with all exchange policies and rules
- Maintaining eligibility for each exchange (geographic restrictions, age requirements, etc.)
- Understanding prohibited trading practices (wash trading, market manipulation, etc.)
- Keeping your exchange accounts in good standing

**CARBS does not:**
- Automatically accept Terms of Service on your behalf
- Monitor changes to exchange policies
- Guarantee compliance with any exchange's rules
- Represent that its trading strategies comply with all exchange policies

---

## Exchange-Specific Requirements

### 1. Binance / Binance.US

**Website:** https://www.binance.com / https://www.binance.us
**ToS URL:** https://www.binance.com/en/terms
**API Terms:** https://www.binance.com/en/terms-api

#### Key Requirements

**Geographic Restrictions:**
- Binance.com: Available in most countries, **RESTRICTED in US** (use Binance.US instead)
- Binance.US: Available only to US residents (excluding NY, TX, VT, HI at various times - check current restrictions)

**Account Requirements:**
- Valid government-issued ID (KYC verification required for API trading)
- 2FA authentication required for API access
- Verified email and phone number

**API Usage Policies:**
- **Rate Limits:** Strictly enforced (weight-based system)
- **Order Rate Limits:** 50 orders per 10 seconds per account
- **Market Making:** Allowed, but must not manipulate markets
- **High-Frequency Trading:** Allowed with proper rate limit compliance
- **API Key Security:** User is responsible for key security; Binance not liable for stolen keys

**Prohibited Activities:**
- Wash trading or self-trading
- Spoofing or layering orders
- Front-running or insider trading
- Market manipulation
- Using multiple accounts to circumvent limits

**Tax Reporting:**
- Binance provides transaction history downloads
- Binance does NOT provide tax forms directly (use CARBS export features)
- User responsible for all tax reporting

**Data Retention:**
- Binance retains transaction history for 90 days in UI
- API access to historical data: 3 months for most endpoints
- **Action Required:** Export and retain your own records (CARBS does this automatically)

#### Compliance Checklist

- [ ] I have read and accepted Binance Terms of Service
- [ ] I have read and accepted Binance API Terms
- [ ] I am not located in a restricted jurisdiction
- [ ] My account has completed KYC verification
- [ ] I have enabled 2FA on my account
- [ ] I understand Binance's rate limits and CARBS respects them
- [ ] I will not engage in prohibited trading activities
- [ ] I understand I am responsible for tax reporting

---

### 2. MEXC Global

**Website:** https://www.mexc.com
**ToS URL:** https://www.mexc.com/user-agreement
**API Documentation:** https://mexcdevelop.github.io/apidocs/

#### Key Requirements

**Geographic Restrictions:**
- Available globally
- **RESTRICTED in**: United States, Canada, Cuba, Crimea, Sevastopol, Iran, Syria, North Korea
- Check current restrictions: https://www.mexc.com/support/articles/360045750731

**Account Requirements:**
- Email verification required
- KYC required for withdrawals and higher limits
- 2FA strongly recommended for API access

**API Usage Policies:**
- **Rate Limits:** 20 requests per 2 seconds per IP
- **Order Rate Limits:** 100 orders per 10 seconds
- **WebSocket Connections:** Maximum 20 subscriptions per connection
- **API Keys:** User manages security; MEXC not liable for compromised keys

**Prohibited Activities:**
- Market manipulation (spoofing, wash trading, layering)
- Using bots that violate fair trading principles
- Circumventing rate limits (CARBS respects rate limits automatically)
- Automated trading that disrupts market fairness

**Tax Reporting:**
- MEXC provides transaction history export (CSV)
- No automatic tax form generation
- User responsible for all tax obligations

**Data Retention:**
- Transaction history available for 6 months via UI
- API historical data: Typically 90 days
- **Action Required:** Export regularly (CARBS handles this)

#### Compliance Checklist

- [ ] I have read and accepted MEXC User Agreement
- [ ] I am not located in a restricted jurisdiction
- [ ] My account has email verification (minimum)
- [ ] I have completed KYC if required for my trading volume
- [ ] I have enabled 2FA for API access
- [ ] I understand MEXC's rate limits and CARBS respects them
- [ ] I will not engage in prohibited trading activities
- [ ] I understand I am responsible for tax reporting

---

### 3. KuCoin

**Website:** https://www.kucoin.com
**ToS URL:** https://www.kucoin.com/agreement
**API Terms:** https://www.kucoin.com/agreement-api

#### Key Requirements

**Geographic Restrictions:**
- Available in most countries
- **RESTRICTED in**: United States (as of 2023 enforcement actions), Canada, mainland China, Iran, North Korea, Cuba, Syria, Crimea
- **Note:** KuCoin faces ongoing regulatory challenges; monitor status

**Account Requirements:**
- Email verification required
- KYC verification required for higher limits and full functionality
- 2FA required for API trading
- API trading passphrase required

**API Usage Policies:**
- **Rate Limits:** Vary by endpoint; spot trading typically 30 requests per 3 seconds
- **Order Rate Limits:** 45 orders per 10 seconds per symbol
- **WebSocket:** 30 subscriptions per connection
- **API Key Security:** User is solely responsible; KuCoin not liable for losses

**Prohibited Activities:**
- Market manipulation (wash trading, spoofing, front-running)
- Automated trading that affects market integrity
- Circumventing security measures or rate limits
- Using multiple accounts to evade restrictions

**Tax Reporting:**
- KuCoin provides trade history export
- No direct tax form generation
- User responsible for all tax reporting in their jurisdiction

**Data Retention:**
- Trade history available for 6 months via UI
- API access to historical orders: 7 days (recent orders), older via separate endpoint
- **Action Required:** Frequent exports recommended (CARBS stores locally)

**⚠️ Regulatory Status Alert:**
- KuCoin is facing regulatory enforcement in multiple jurisdictions
- US persons should NOT use KuCoin (CFTC/FinCEN charges filed 2024)
- Monitor regulatory developments before using this exchange

#### Compliance Checklist

- [ ] I have read and accepted KuCoin User Agreement
- [ ] I have read and accepted KuCoin API Terms
- [ ] I am not located in a restricted jurisdiction (especially NOT a US person)
- [ ] I have completed KYC verification
- [ ] I have enabled 2FA on my account
- [ ] I have created an API trading passphrase
- [ ] I understand KuCoin's rate limits and CARBS respects them
- [ ] I am aware of KuCoin's regulatory challenges
- [ ] I will not engage in prohibited trading activities
- [ ] I understand I am responsible for tax reporting

---

## Common Compliance Requirements

### Across All Exchanges

**Age Requirements:**
- Minimum age: 18 years old (or age of majority in your jurisdiction)
- Some exchanges require 21+ in certain regions

**Identity Verification (KYC):**
- Government-issued photo ID required
- Proof of address may be required for higher limits
- Selfie verification (liveness check) increasingly common

**Anti-Money Laundering (AML):**
- Exchanges must comply with local AML regulations
- Suspicious activity may trigger account reviews or freezes
- Large transactions may require source of funds documentation

**API Security:**
- **Never share your API keys with anyone**
- Use API key restrictions (IP whitelist, withdrawal disabled, etc.)
- Rotate API keys periodically (recommended: every 90 days)
- Enable read-only access where possible (CARBS needs trading permissions)

**Prohibited Trading Patterns:**
- **Wash Trading:** Trading with yourself to create fake volume
- **Spoofing:** Placing orders you intend to cancel to manipulate price
- **Layering:** Multiple spoofing orders
- **Front-Running:** Trading ahead of large orders you're aware of
- **Market Manipulation:** Coordinated price manipulation

---

## CARBS-Specific Compliance

### How CARBS Helps You Stay Compliant

**Rate Limit Enforcement:**
- CARBS implements rate limiters for each exchange
- Automatically throttles requests to stay within limits
- Queues orders when approaching limits

**Record Keeping:**
- All trades stored locally in PostgreSQL database
- Audit logs retained for 7 years (IRS requirement)
- Transaction history exportable for tax purposes

**Order Behavior:**
- CARBS does not engage in wash trading (trades across different exchanges)
- All orders are legitimate arbitrage opportunities
- No spoofing or layering (orders are intended to execute)

**API Key Management:**
- API keys stored in encrypted environment variables
- Keys never logged or transmitted insecurely
- User controls key permissions (recommended: trading only, no withdrawals)

### What CARBS Cannot Do

**CARBS does NOT:**
- Monitor exchange ToS changes (you must do this)
- Guarantee compliance with exchange policies
- Prevent you from violating exchange rules
- Accept legal liability for exchange violations
- Automatically update when exchanges change policies

**Your Responsibilities:**
- Review exchange ToS quarterly (set calendar reminder)
- Monitor exchange announcements for policy changes
- Ensure your trading strategies comply with each exchange
- Maintain valid KYC status on all exchanges
- Keep API keys secure and rotated

---

## Compliance Monitoring Schedule

### Quarterly Review (Jan 15, Apr 15, Jul 15, Oct 15)

**Check for ToS Updates:**
1. Visit each exchange's Terms of Service page
2. Check "Last Updated" date
3. Review any changes for compliance impact
4. Update this document if material changes

**Verify Account Standing:**
1. Log into each exchange
2. Check for any compliance notifications
3. Verify KYC status remains valid
4. Review any new geographic restrictions

**API Key Rotation:**
1. Generate new API keys on each exchange
2. Update `.env` file with new keys
3. Test CARBS connection
4. Delete old API keys

**Record Keeping:**
1. Verify CARBS database backup is current
2. Export transaction history from each exchange
3. Compare CARBS records with exchange records
4. Archive exports with tax records

---

## Regulatory Updates to Monitor

### Exchange-Specific

**Binance:**
- SEC enforcement actions and settlements
- State-level restrictions (particularly Binance.US)
- International regulatory developments

**MEXC:**
- Geographic expansion/restrictions
- Regulatory licensing status
- User agreement changes

**KuCoin:**
- **ACTIVE ENFORCEMENT:** CFTC and FinCEN charges (2024)
- Potential settlement terms affecting US users
- Licensing status in various jurisdictions

### Industry-Wide

**United States:**
- SEC cryptocurrency regulation (securities vs. commodities)
- CFTC oversight of crypto derivatives
- FinCEN AML requirements for exchanges
- State-level money transmitter laws

**International:**
- EU MiCA (Markets in Crypto-Assets) regulation
- UK FCA cryptocurrency regulation
- Asian regulatory developments

---

## Emergency Procedures

### If Your Exchange Account Is Restricted

1. **Stop Trading Immediately:** Disable CARBS for that exchange
2. **Contact Exchange Support:** Follow their dispute resolution process
3. **Document Everything:** Save all communications
4. **Export Records:** Download full transaction history before potential suspension
5. **Seek Legal Advice:** If large amounts are at stake

### If an Exchange Changes ToS

1. **Review Changes:** Understand what's different
2. **Assess CARBS Compatibility:** Does CARBS violate new terms?
3. **Update Configuration:** Adjust CARBS settings if needed
4. **Consider Alternatives:** May need to switch exchanges
5. **Update This Document:** Reflect changes in this compliance guide

### If Regulatory Action Occurs

1. **Preserve Records:** Keep all CARBS database backups
2. **Stop Trading:** Cease operations until situation clarifies
3. **Export Everything:** Get data while exchanges are still operational
4. **Consult Professionals:** Lawyer and accountant
5. **File Taxes:** Ensure all prior year taxes were properly filed

---

## Resources

### Exchange Support

- **Binance Support:** https://www.binance.com/en/support
- **MEXC Support:** https://www.mexc.com/support/sections/360000291333
- **KuCoin Support:** https://support.kucoin.plus/hc/en-us

### Regulatory Resources

- **CFTC (US):** https://www.cftc.gov/digitalassets
- **SEC (US):** https://www.sec.gov/spotlight/cybersecurity-enforcement-actions
- **FinCEN (US):** https://www.fincen.gov/resources/statutes-and-regulations/guidance/application-fincens-regulations-certain-business
- **IRS Cryptocurrency:** https://www.irs.gov/businesses/small-businesses-self-employed/virtual-currencies

### Legal Disclaimers

**This document is for informational purposes only and does not constitute legal advice.** You should:
- Consult with a licensed attorney regarding compliance obligations
- Consult with a certified tax professional regarding tax obligations
- Conduct your own due diligence on each exchange
- Monitor regulatory developments in your jurisdiction

**CARBS developers are not responsible for:**
- Your compliance with exchange Terms of Service
- Any losses resulting from exchange policy violations
- Changes to exchange policies after this document was created
- Regulatory enforcement actions against users or exchanges

---

## Document Version History

| Version | Date       | Changes                           | Author     |
|---------|------------|-----------------------------------|------------|
| 1.0     | 2025-12-18 | Initial creation                  | CARBS Team |

**Next Review Date:** 2026-01-15
