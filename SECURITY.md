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

## V0.4 Tool Safety Model

- **No execution tools**: there is no shell, Python-eval or OS-command
  tool, and `SafetyClass` has no variant that would allow one.
- **Strict schemas**: tools reject unknown fields and wrong types;
  every failure becomes a `ToolResult`, never an exception escape.
- **Memory credential refusal**: the memory tool refuses content
  resembling passwords, keys, tokens or card numbers — no secure
  secrets system exists, so secrets never enter the database.
- **Log hygiene**: tool execution logs names and success flags only.
  Arguments and raw results are never logged.
- **Paper tool**: submits refused unless paper mode is enabled;
  proposals and submits both pass `RiskEngine`; rejections carry
  structured explanations (`risk.decision/reason/violations`).
- **File tools**: confined to one root; absolute paths, `..` escapes
  and sensitive filenames (`.env`, keys, tokens, credentials) refused;
  reads capped (100 KiB), oversized drawings/workbooks refused outright.
- **Web tool**: http(s) GET only; link-local/metadata addresses refused;
  2 MiB cap; no JavaScript, no forms, no cookies, no auth.
- **API tools endpoint**: same Bearer auth as all endpoints; unknown
  tools return 422, never execution.

**LIVE TRADING DOES NOT EXIST.** No broker order API, no exchange
trading API, no wallet, no deposit/withdrawal — anywhere in the tree.

## Exposing the API Beyond Localhost

The API binds `127.0.0.1` with plain HTTP by default. That is safe on
a single-user machine and unsafe anywhere else. To serve it remotely:

1. **Never expose the stdlib server directly.** Put it behind a
   reverse proxy (Caddy, nginx) that terminates TLS — the app has no
   TLS support and must never gain `ssl` bypasses or `verify=False`
   equivalents.
2. **Example (Caddy):** `yourdomain.tld { reverse_proxy 127.0.0.1:PORT }`
   gets you automatic HTTPS. Firewall everything except 443.
3. **Keep Bearer auth on.** TLS encrypts but does not authenticate;
   the token is still required on every request.
4. **Do not bind `0.0.0.0` in the app** unless the host firewall
   restricts ingress to the proxy.

## API Token Rotation

Tokens are bearer credentials: whoever holds one has full API access.

1. **Generate:** `python -c "import secrets; print(secrets.token_hex(32))"`
   (64 hex chars, 256 bits). Never reuse passwords or short tokens.
2. **Store:** environment (`WELLPAID_API_TOKEN`) or a secrets manager.
   Never in code, chat logs, screenshots, or the repo.
3. **Rotate:** replace the env value and restart the server. Old tokens
   die instantly — there is no grace period, allowlist, or revocation
   list by design (single-token model).
4. **If leaked:** rotate immediately, then check paper account state
   (`GET /account`, `/orders`) for unexpected activity. There is no
   live money at risk, but paper state may need `reset`.
5. **Cadence:** rotate on personnel change, on any suspected exposure,
   and at least every 90 days.

## Incident Response

If credentials are compromised:

1. Immediately revoke all API keys
2. Check logs for unauthorized access
3. Review all recent trades
4. Reset all credentials
5. Notify relevant parties
