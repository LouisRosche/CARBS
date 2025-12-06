# Exchange Selection Guide for Small Capital

This guide helps you choose the right exchange(s) for starting with small capital ($100-$1000).

## TL;DR Recommendations

| Capital | Primary Exchange | Why |
|---------|-----------------|-----|
| <$100 | MEXC | 0% maker fees |
| $100-$500 | Binance | Low fees + best liquidity |
| $500-$5000 | Binance + Kraken | Diversification |
| >$5000 | Multi-exchange | Full arbitrage capability |

---

## Why Exchange Choice Matters for Small Capital

With $100, a **single trade costs you**:

| Exchange | Round-Trip Fee | You Pay | % of Capital |
|----------|---------------|---------|--------------|
| Coinbase | 1.0% (maker) | $1.00 | 1.0% |
| Kraken | 0.32% | $0.32 | 0.32% |
| Binance | 0.20% | $0.20 | 0.20% |
| MEXC (limit) | 0% | $0.00 | 0.0% |

**10 trades on Coinbase = $10 in fees = 10% of your capital gone.**

---

## Exchange Deep Dives

### 1. MEXC - Best for Tiny Capital

**Fees:**
- Maker: **0%** (limit orders)
- Taker: 0.1% (market orders)

**Pros:**
- Zero maker fees = more profit kept
- No minimum deposit
- Wide range of altcoins
- Good for practicing

**Cons:**
- Less liquidity than Binance
- Not available in some countries
- Newer exchange (less track record)
- No fiat on-ramp in some regions

**Best for:** Learning, testing strategies, altcoin trading

**Setup:**
1. Go to mexc.com
2. Register with email
3. Enable 2FA immediately
4. Complete KYC for withdrawals
5. **Enable API with trade-only permissions**

---

### 2. Binance - Best Overall

**Fees:**
- Maker: 0.1% (0.075% with BNB)
- Taker: 0.1% (0.075% with BNB)

**Pros:**
- Best liquidity globally
- Most trading pairs
- Advanced features
- Lowest effective fees with BNB discount
- Great API

**Cons:**
- Not available in some US states
- Can be overwhelming for beginners
- Regulatory uncertainty in some regions

**Best for:** Anyone serious about trading

**Fee Optimization:**
1. Hold some BNB in account
2. Enable "Use BNB for fees" in settings
3. This gives 25% fee discount

**Setup:**
1. Go to binance.com (or binance.us if in US)
2. Register and complete KYC
3. Enable 2FA (Google Auth preferred)
4. Buy small amount of BNB
5. Create API key:
   - Go to API Management
   - Create new key
   - Enable: Read, Spot Trading
   - **Disable: Withdrawals, Margin, Futures**
   - Add IP whitelist

---

### 3. Kraken - Best for Security

**Fees:**
- Maker: 0.16%
- Taker: 0.26%

**Pros:**
- Never been hacked
- Strong regulatory compliance
- Fiat on/off ramps
- Good customer support
- US friendly

**Cons:**
- Higher fees than Binance
- Fewer trading pairs
- Can have withdrawal delays

**Best for:** Security-conscious traders, US users

---

### 4. KuCoin - Good Alternative

**Fees:**
- Maker: 0.1%
- Taker: 0.1%

**Pros:**
- No KYC required for small amounts
- Wide altcoin selection
- Trading bot features built-in
- Low fees

**Cons:**
- Not licensed in US (use at own risk)
- Less liquidity than Binance
- Occasional withdrawal issues

---

### 5. Bybit - For Futures (Advanced)

**Fees:**
- Spot Maker: 0.1%
- Spot Taker: 0.1%
- Futures: 0.01% maker / 0.06% taker

**Pros:**
- Excellent for futures trading
- Capital efficient (leverage)
- Good mobile app
- Copy trading feature

**Cons:**
- Futures = high risk
- Not for beginners
- Not available in US

**Warning:** Futures with small capital is very risky. The leverage that makes it capital-efficient also amplifies losses. Start with spot trading.

---

## Exchange Setup Checklist

### Security (Do This First!)

- [ ] Use unique, strong password
- [ ] Enable 2FA (Google Authenticator, not SMS)
- [ ] Save 2FA backup codes securely
- [ ] Enable anti-phishing code
- [ ] Whitelist withdrawal addresses
- [ ] Enable login notifications

### API Key Setup

- [ ] Create dedicated API key for CARBS
- [ ] Enable only: Read + Spot Trading
- [ ] **Disable: Withdrawals**
- [ ] Add IP whitelist (your server IP)
- [ ] Save key securely (you only see secret once)
- [ ] Test with paper trading first

### Funding

- [ ] Start with bank transfer (lowest fees)
- [ ] Avoid credit card deposits (high fees)
- [ ] Consider stablecoin transfer from another exchange
- [ ] Keep records for taxes

---

## Multi-Exchange Strategy

For arbitrage, you need funds on multiple exchanges. With $100:

### Phase 1: Single Exchange (Learning)
- Start on MEXC or Binance
- Paper trade to learn system
- Graduate to live with $20-50

### Phase 2: Two Exchanges ($200+)
- Split: 60% Binance, 40% MEXC or KuCoin
- Enables basic cross-exchange arbitrage
- More opportunities

### Phase 3: Three+ Exchanges ($500+)
- Add Kraken or Bybit
- Full arbitrage capability
- Rebalance weekly

---

## Deposit Methods Comparison

| Method | Speed | Fees | Limit |
|--------|-------|------|-------|
| Bank Transfer (ACH) | 1-5 days | Free-Low | High |
| Wire Transfer | 1-2 days | $10-30 | Very High |
| Debit Card | Instant | 2-4% | Medium |
| Credit Card | Instant | 3-5% | Medium |
| Crypto Transfer | 10-60 min | Network fee | Unlimited |

**Recommendation:** Bank transfer for fiat, or buy stablecoin (USDC) elsewhere and transfer.

---

## Geographic Restrictions

### US Traders
- **Use:** Binance.US, Coinbase, Kraken, Gemini
- **Avoid:** Binance.com, KuCoin (gray area), Bybit

### EU Traders
- **Use:** Binance, Kraken, Bitstamp
- **Check:** MiCA compliance requirements

### UK Traders
- **Use:** Kraken, Bitstamp
- **Limited:** Binance (restricted since 2021)

### Other Regions
- Check local regulations
- Use exchanges with proper licensing

---

## Starting Capital Allocation

### With $100:
```
$100 on single exchange (MEXC or Binance)
- Learn the system
- Paper trade first
- Graduate to live with $20 test
```

### With $500:
```
$300 Binance (primary)
$200 MEXC or KuCoin (secondary)
- Cross-exchange opportunities
- Rebalance monthly
```

### With $1000:
```
$500 Binance (primary)
$300 Kraken (fiat off-ramp)
$200 MEXC (altcoins)
- Full strategy capability
- Weekly rebalancing
```

---

## Fee Comparison Calculator

To calculate if a trade is profitable:

```
Profit needed = (Entry Fee %) + (Exit Fee %) + Slippage Buffer

Example on Binance with BNB discount:
- Entry: 0.075%
- Exit: 0.075%
- Slippage: 0.05%
- Total: 0.2%

Your trade must make > 0.2% to profit.
```

For a $100 position:
- 0.2% of $100 = $0.20
- Need price to move more than 0.2% in your favor

---

## Quick Start Steps

### 1. Create Account (15 minutes)
Choose your exchange based on capital/location.

### 2. Complete KYC (1-3 days)
Required for deposits/withdrawals.

### 3. Enable Security (10 minutes)
2FA, anti-phishing, whitelist addresses.

### 4. Create API Key (5 minutes)
Read + Trade only. No withdrawals. IP whitelist.

### 5. Make Test Deposit ($10-20)
Verify everything works.

### 6. Configure CARBS
```bash
python -m src.cli.commands creds add binance
# Enter your API key and secret
```

### 7. Paper Trade First!
Run in paper mode for at least a week.

---

## Common Mistakes to Avoid

1. **Using market orders** - Fees are higher, slippage hurts
2. **Overtrading** - More trades = more fees
3. **Ignoring fees** - They compound quickly
4. **No stop losses** - One bad trade can wipe gains
5. **FOMO trading** - Chasing pumps with small capital
6. **Keeping funds on exchange** - Only keep what you're trading
7. **Skipping paper trading** - Test before risking real money

---

## Summary

| Priority | Action |
|----------|--------|
| 1 | Choose exchange (MEXC for <$100, Binance for >$100) |
| 2 | Enable all security features |
| 3 | Create trade-only API key with IP whitelist |
| 4 | Deposit via bank transfer |
| 5 | Paper trade for 1 week |
| 6 | Start live with 20% of capital |
| 7 | Scale up after consistent profits |

Remember: With small capital, your goal is to **learn** and **not lose money**, not to get rich quick. Treat it as tuition for your trading education.
