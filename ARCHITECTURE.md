# WellPaiD Trader - Architecture

## System Overview

WellPaiD Trader is a modular personal AI agent designed for trading research, strategy development, and controlled trading execution.

## Core Components

### 1. Core Agent (`agent/core/`)

- **main.py** - Interactive CLI agent with command processing
- **config.py** - Configuration management with safety defaults
- **router.py** - Command routing system
- **tasks.py** - Task management with persistence

### 2. Data Layer (`agent/data/`)

- **memory.py** - Local memory storage with search capabilities

### 3. Logging (`agent/logs/`)

- **logging_config.py** - Secure logging with sensitive data filtering

### 4. Risk Engine (`agent/risk/`)

- **engine.py** - Risk management with authority to approve/reject trades

### 5. Trading (`agent/trading/`)

- **research.py** - Market data analysis and strategy research
- **paper.py** - Simulated trading with fake money

## Data Flow

```
User Input
    ↓
Core Agent
    ↓
Command Router
    ↓
Module Handlers
    ↓
Risk Engine (for trading)
    ↓
Execution (paper/live)
```

## Safety Architecture

### Multi-Layer Protection

1. **Configuration Layer** - All trading disabled by default
2. **Risk Engine Layer** - Can veto any trade decision
3. **Execution Layer** - Paper trading isolated from real brokers
4. **Monitoring Layer** - Logs all actions for audit

### Trading Safety Controls

- `TRADING_ENABLED` - Master switch (default: false)
- `PAPER_TRADING_ENABLED` - Paper trading switch (default: false)
- `LIVE_TRADING_ENABLED` - Live trading switch (default: false)

**Live trading requires ALL three to be true AND explicit user authorization.**

## Module Interfaces

### DataProvider Interface

```python
class DataProvider(ABC):
    def get_historical_data(symbol, asset_type, start_date, end_date) -> MarketData
    def get_current_price(symbol, asset_type) -> float
```

### StrategyBase Interface

```python
class StrategyBase(ABC):
    def generate_signals(data: MarketData) -> list[Signal]
    def get_name() -> str
```

### RiskEngine Interface

```python
class RiskEngine:
    def evaluate(proposal: TradeProposal) -> RiskCheck
    def record_trade(proposal: TradeProposal) -> None
```

## Storage

SQLite (write-through, auto-closing connections; a legacy V1 JSON file
at the same path is moved aside to `<name>.bak`, never parsed):

- **Memory**: SQLite (`agent/data/memory.db`)
- **Tasks**: SQLite (`agent/data/tasks.db`)
- **Paper Trading**: SQLite (`agent/data/paper_trading.db`)
- **Logs**: Text files (`agent/logs/wellpaid.log`)

## Testing Strategy

- Unit tests for each module
- Integration tests for safety controls
- Verify trading remains disabled by default
- Verify risk engine authority
