# Exchange API Key Setup

## Security Best Practices

1. **Never commit API keys to git**
2. **Use environment variables only**
3. **Enable IP whitelisting on exchanges**
4. **Restrict API permissions** (trade + read only, no withdrawals)
5. **Rotate keys regularly**

## Binance

1. Log into Binance
2. Navigate to API Management
3. Create new API key
4. Enable "Enable Spot & Margin Trading"
5. **Disable** "Enable Withdrawals"
6. Add your VPS IP to whitelist
7. Copy key and secret to `.env`

## Coinbase

1. Log into Coinbase Pro
2. Navigate to API settings
3. Create API key with "Trade" permission only
4. Copy credentials to `.env`

## Kraken

1. Log into Kraken
2. Settings → API
3. Generate new key
4. Enable "Query Funds" and "Create & Modify Orders"
5. **Disable** "Withdraw Funds"
6. Copy to `.env`
