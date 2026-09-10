# WellPaiD Trader

A modular personal AI agent for trading research, strategy development, and automated trading (with strict safety controls).

## Quick Start

### 1. Activate Virtual Environment

```powershell
cd C:\WellPaiD-Trader
.\.venv\Scripts\Activate.ps1
```

### 2. Run the Agent

```powershell
python -m agent.core.main
```

### 3. Available Commands

- `hello` - Greet the agent
- `help` - Show available commands
- `status` - Show system status
- `exit` - Exit the agent

## Configuration

Copy `.env.example` to `.env` and customize as needed:

```powershell
copy .env.example .env
```

**IMPORTANT:** All trading is disabled by default. Never enable live trading without explicit authorization.

## Project Structure

```
WellPaiD-Trader/
├── agent/
│   ├── api/              # Authenticated HTTP API (Bearer token)
│   ├── core/             # Agent, config, router, tasks, storage
│   ├── data/             # Memory, storage
│   ├── logs/             # Logging system
│   ├── risk/             # Risk engine (quantity + notional limits)
│   ├── tools/            # External tools
│   └── trading/          # Research, paper trading, read-only brokers
├── tests/              # Test suite (56 tests)
├── .env.example        # Configuration template
└── README.md           # This file
```

## Market Data (read-only)

No keys required, stdlib only. No trading endpoints are ever called:

- Stocks/ETFs/forex worldwide: `StooqDataProvider` (`agent/trading/brokers.py`)
- Crypto: `CoinbaseDataProvider` (public spot + candles)

```python
from agent.trading.brokers import StooqDataProvider
from agent.trading.research import AssetType
from datetime import datetime, timedelta

provider = StooqDataProvider()
data = provider.get_historical_data(
    "AAPL", AssetType.STOCK,
    datetime.now() - timedelta(days=30), datetime.now(),
)
print(provider.get_current_price("siemens.de", AssetType.STOCK))
```

## HTTP API

Bearer-token authenticated, localhost by default. `POST /orders` works
only when `TRADING_ENABLED` and `PAPER_TRADING_ENABLED` are both true.

```powershell
$env:WELLPAID_API_TOKEN = "<generate with secrets.token_hex(32)>"
python -c "from agent.api.server import create_server; create_server(api_token='...').serve_forever()"
# GET /status /account /positions /orders /risk /price?symbol=AAPL
# POST /orders {"symbol":"AAPL","side":"buy","quantity":10,"current_price":150.0}
```

## Safety Features

- **Trading disabled by default** - All trading must be explicitly enabled
- **Risk engine authority** - Can veto any trade, including AI proposals
- **Paper trading isolation** - Never connects to real brokers
- **No secrets in code** - API keys stored in environment variables only

## Testing

Run all tests:

```powershell
python -m unittest discover tests -v
```

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [SECURITY.md](SECURITY.md) - Security practices
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development roadmap

## License

Private project - All rights reserved.
