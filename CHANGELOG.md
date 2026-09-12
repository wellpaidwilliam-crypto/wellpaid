# Changelog

All notable changes to WellPaiD Trader, newest first. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
`0.MINOR` while research-only (no live trading exists at any version).

## [Unreleased]

## [0.10.0] - 2026-09-12

### Added
- CLI startup reminders line (overdue + due-today counts, silent otherwise)
- API `GET /tasks/due` (404 when the tasks backend is absent)

### Tests
- 130 passing

## [0.9.0] - 2026-09-12

### Added
- `memory export` action (markdown|json backup payload, 500 cap)

### Tests
- 126 passing

## [0.8.0] - 2026-09-12

### Added
- No-lookahead incremental backtest engine with equity curve,
  max drawdown and Sharpe statistics
- Walk-forward folds (2..5, no tuning — regime-consistency check)

### Tests
- 125 passing

## [0.7.0] - 2026-09-12

### Added
- Backtester fees/slippage modeling (`fee_bps`, `slippage_bps` per fill,
  tracked in `total_fees`) and seeded deterministic mock data (`seed`)
- Webfetch TTL cache (10 min, 50 entries, `fresh` bypass)
- Memory search ranked by term frequency with recency tiebreak
- GitHub Pages static site (`docs/`, `.nojekyll`)

### Changed
- `backtest` tool accepts `seed`/`fee_bps`/`slippage_bps`; assumptions
  honestly report modeled costs

### Security
- API remote-exposure guidance (TLS via reverse proxy, never expose
  the stdlib server directly) and token rotation procedure (90-day cadence)

### Tests
- 118 passing (110 preserved + 8 new)

## [0.6.0] - 2026-09-12

### Added
- `docx` tool (.docx info/text/tables via stdlib zip/xml)
- Tasks `due_date` passthrough (YYYY-MM-DD) and `due` action with overdue flags

### Changed
- CI on current GitHub Actions majors (checkout v5, setup-python v6);
  Node-20 deprecation warnings cleared

### Tests
- 110 passing (107 preserved + 3 new)

## [0.5.0] - 2026-09-11

### Added
- `files` tool (root sandbox, traversal + sensitive-name refusal, caps)
- `sheets` tool (.xlsx via stdlib zip; preview/stats; formulas never evaluated)
- `pdf` tool (optional pypdf/pdfplumber; graceful install hint)
- `dxf` tool (read-only inventory: entities, layers, extents)
- `webfetch` tool (GET-only, 2 MiB cap, no JS, metadata-IP refusal)
- `SafetyClass.LOCAL_READ`; registry/CLI/API pick up tools automatically

### Tests
- 107 passing (94 preserved + 13 new)

## [0.4.0] - 2026-09-11

### Added
- Tool abstraction (`Tool`, `ToolResult`, `SafetyClass` — no exec tools exist)
- `ToolRegistry` (register/get/list/safe execute, redacted logging)
- Catalog: calculator, system_status, memory (+credential refusal), tasks,
  market_data, backtest (honesty-labeled), paper_account (risk-gated)
- Structured risk explanations (`format_rejection`; veto logic untouched)
- API `GET /tools` + `POST /tools/execute` under Bearer auth
- CLI `tools`/`run` commands and `remember`/`remind me`/`price` shortcuts

### Tests
- 94 passing (57 preserved + 37 new)

## [0.3.0] - 2026-09-10

### Added
- Notional risk limits (per-trade + portfolio) and `RiskEngine.from_config()`
- SQLite persistence for paper/tasks/memory (write-through, auto-closing)
- Read-only brokers: Stooq (global stocks) + Coinbase (crypto), stdlib only
- Bearer-token HTTP API (localhost default, paper-gated orders)
- GitHub Actions CI (ubuntu + windows × Python 3.11–3.14)

### Fixed
- Fail-closed config validation; risk input validation; paper funds/short
  guards; logging redaction of format args; atomic JSON writes

### Tests
- 57 passing

[Unreleased]: https://github.com/wellpaidwilliam-crypto/wellpaid/compare/v0.10.0...master
[0.10.0]: https://github.com/wellpaidwilliam-crypto/wellpaid/releases/tag/v0.10.0
[0.9.0]: https://github.com/wellpaidwilliam-crypto/wellpaid/releases/tag/v0.9.0
[0.8.0]: https://github.com/wellpaidwilliam-crypto/wellpaid/releases/tag/v0.8.0
[0.7.0]: https://github.com/wellpaidwilliam-crypto/wellpaid/releases/tag/v0.7.0
[0.6.0]: https://github.com/wellpaidwilliam-crypto/wellpaid/releases/tag/v0.6.0
[0.5.0]: https://github.com/wellpaidwilliam-crypto/wellpaid/releases/tag/v0.5.0
[0.4.0]: https://github.com/wellpaidwilliam-crypto/wellpaid/releases/tag/v0.4.0
[0.3.0]: https://github.com/wellpaidwilliam-crypto/wellpaid/releases/tag/v0.3.0
