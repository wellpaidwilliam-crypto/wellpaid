# WellPaiD Trader - Development Roadmap

## Version History

### V1 - Core Agent (Current)

- ✅ Interactive CLI agent
- ✅ Configuration system
- ✅ Logging system
- ✅ Command router
- ✅ Memory foundation
- ✅ Task manager
- ✅ Trading research foundation
- ✅ Risk engine
- ✅ Paper trading engine
- ✅ Comprehensive tests

### V0.4 - Personal AI Agent Foundation (Current)

- ✅ Tool abstraction (`Tool`, `ToolResult`, `SafetyClass` — no exec tools)
- ✅ ToolRegistry (register/get/list/safe execute, redacted logging)
- ✅ Memory/task tools over existing SQLite stores (+ credential refusal)
- ✅ Read-only market-data tool (Stooq/Coinbase, graceful offline)
- ✅ Research backtest tool (mandatory HISTORICAL ≠ prediction labeling)
- ✅ Paper-account tool (propose/submit via risk veto, PAPER-labeled)
- ✅ Structured risk explanations (`format_rejection`, veto untouched)
- ✅ API `/tools` + `/tools/execute` (same Bearer auth, paper still gated)
- ✅ CLI `tools`/`run` + `remember`/`remind me`/`price` shortcuts
- ✅ 94 automated tests (57 V0.3 preserved + 37 new)

Stdlib-only dependency policy upheld: no third-party packages added.

### V0.5 - Personal-Agent Depth, Batch A

- ✅ files tool (root sandbox, traversal + sensitive-name refusal)
- ✅ sheets tool (.xlsx via stdlib zipfile; stats/preview; no formula eval)
- ✅ pdf tool (optional pypdf/pdfplumber; graceful hint, stays optional)
- ✅ dxf tool (read-only inventory: entities, layers, extents; 50 MiB cap)
- ✅ webfetch tool (GET-only, 2 MiB cap, no JS, link-local refused)
- ✅ 107 automated tests (94 V0.4 preserved + 13 new)

### V0.6 - Personal-Agent Depth, Batch B

- ✅ CI on current GitHub Actions majors (checkout v5, setup-python v6)
- ✅ docx tool (.docx via stdlib zip/xml: info/text/tables)
- ✅ tasks due_date passthrough (YYYY-MM-DD) + `due` action with overdue flags

### V0.7 - Realism, Memory, Hardening + Site

- ✅ Backtester fees/slippage (bps per fill) + seeded deterministic mock data
- ✅ Webfetch TTL cache (10 min, 50 entries, `fresh` bypass)
- ✅ Memory search ranked by term frequency, recency tiebreak
- ✅ API remote-exposure + token rotation docs (TLS via reverse proxy)
- ✅ GitHub Pages site (`docs/`, static, `.nojekyll`)

### V0.8 - Backtest Depth

- ✅ No-lookahead incremental engine (strategy sees only past bars)
- ✅ Per-bar equity curve, max drawdown, Sharpe (0.0 when undefined)
- ✅ Walk-forward folds (2..5, no tuning — regime-consistency check)
- ✅ Tool reports stats + folds; honesty labeling unchanged

### V0.9 - Memory Export (Current)

- ✅ `memory export` action (markdown|json backup payload, 500 cap)

### V2 - Enhanced Research

- [ ] Real market data integration
- [ ] More technical indicators
- [ ] Strategy optimization
- [ ] Performance analytics
- [ ] Visualization tools

### V3 - Advanced Backtesting

- [ ] Monte Carlo simulation
- [ ] Walk-forward optimization
- [ ] Multi-asset backtesting
- [ ] Slippage modeling
- [ ] Transaction cost analysis

### V4 - Enhanced Paper Trading

- [ ] Multiple paper accounts
- [ ] Portfolio tracking
- [ ] Advanced order types
- [ ] Real-time simulation
- [ ] Performance reporting

### V5 - Controlled Live Trading

- [ ] Broker API integration
- [ ] Order management system
- [ ] Position management
- [ ] Real-time monitoring
- [ ] Emergency shutdown

## Development Principles

### Safety First

1. **Trading disabled by default** - Must be explicitly enabled
2. **Risk engine authority** - Can veto any trade
3. **Paper trading isolation** - Never touches real money
4. **Audit logging** - All actions recorded

### Incremental Development

1. **One phase at a time** - Complete before moving on
2. **Test everything** - No untested code
3. **Review before proceeding** - Verify each phase
4. **Document changes** - Update documentation

### Code Quality

1. **Type hints** - All functions typed
2. **Docstrings** - Clear documentation
3. **Error handling** - Graceful failure
4. **Modular design** - Loose coupling

## Testing Strategy

### Unit Tests

- Test each module independently
- Verify all public methods
- Test error conditions
- Verify edge cases

### Integration Tests

- Test module interactions
- Verify safety controls
- Test end-to-end workflows
- Verify data persistence

### Safety Tests

- Verify trading disabled by default
- Verify risk engine authority
- Verify paper trading isolation
- Verify no real orders placed

## Configuration Management

### Environment Variables

```env
APP_NAME=WellPaiD Trader
ENVIRONMENT=development
LOG_LEVEL=INFO
TRADING_ENABLED=false
PAPER_TRADING_ENABLED=false
LIVE_TRADING_ENABLED=false
```

### Configuration Validation

- Validate on startup
- Check trading safety
- Verify credentials
- Log configuration state

## Logging

### Log Levels

- **DEBUG** - Detailed debugging information
- **INFO** - General information
- **WARNING** - Warning messages
- **ERROR** - Error messages
- **CRITICAL** - Critical errors

### Log Rotation

- 5MB maximum file size
- 5 backup files
- Automatic rotation

## Performance Considerations

### Current Limitations (updated V0.3)

- SQLite stores (crash-safe, single-writer; not suitable for high-frequency)
- Single-threaded execution (API uses a threaded server for I/O only)
- In-memory processing

### Future Optimizations

- Postgres for concurrent writers
- Async processing
- Caching layer
- Database indexing

## Deployment

### Development

```powershell
python -m agent.core.main
```

### Testing

```powershell
python -m unittest discover tests -v
```

### Production

Not yet implemented - research only.
