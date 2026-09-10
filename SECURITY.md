# WellPaiD Trader - Security

## Security Principles

1. **No real money at risk** - Trading is disabled by default
2. **No secrets in code** - API keys stored in environment variables only
3. **Risk engine authority** - Can veto any trade, including AI proposals
4. **Audit logging** - All actions are logged for review

## Credential Management

### What We Never Store in Code

- API keys
- API secrets
- Passwords
- Broker credentials
- Exchange credentials
- Private keys
- Access tokens

### Where Credentials Are Stored

- Environment variables (preferred)
- `.env` file (local development only)
- Never committed to version control

### Example `.env` File

```env
EXCHANGE_API_KEY=
EXCHANGE_API_SECRET=
```

## Trading Safety Controls

### Default State

All trading is **DISABLED** by default:

```
TRADING_ENABLED=false
PAPER_TRADING_ENABLED=false
LIVE_TRADING_ENABLED=false
```

### Safety Requirements

Live trading requires:

1. `TRADING_ENABLED=true`
2. `LIVE_TRADING_ENABLED=true`
3. Explicit user authorization
4. Valid API credentials
5. Risk engine approval

### Risk Engine Authority

The risk engine has **absolute authority** over trade execution:

- Can approve or reject ANY trade
- AI cannot override risk engine decisions
- Risk engine is the final authority

### Risk Limits

- Maximum position size
- Maximum daily loss
- Maximum drawdown
- Maximum trades per day
- Total exposure limits

## Paper Trading Isolation

Paper trading is completely isolated:

- No broker connections
- No real orders placed
- Uses simulated money only
- Clearly marked as "PAPER TRADING"

## Logging Security

### What We Log

- User commands
- System status
- Trade proposals
- Risk decisions
- Errors and warnings

### What We Never Log

- API keys
- Passwords
- Secrets
- Credentials
- Private keys

### Sensitive Data Filter

All logs pass through a sensitive data filter that redacts:

- api_key
- api_secret
- password
- token
- secret
- credential
- private_key
- access_key

## Development Guidelines

1. **Never commit secrets** to version control
2. **Use environment variables** for credentials
3. **Test safety controls** before enabling trading
4. **Verify risk engine** can reject trades
5. **Review logs** regularly for anomalies

## Incident Response

If credentials are compromised:

1. Immediately revoke all API keys
2. Check logs for unauthorized access
3. Review all recent trades
4. Reset all credentials
5. Notify relevant parties
