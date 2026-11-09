# Architecture overview

## Current dataflow

```text
Provider stream/REST
  → candle pipeline
  → market event bus
  → explicit option strategies on each configured timeframe
  → shared order manager and position watcher
  → trade-event ledger and performance reports
```

With `TRADING_STORAGE_BACKEND=r2`, candles and objects use R2 Parquet, DuckDB,
and the Postgres file catalog. Trade events and durable config/JSON state use
Postgres. `local` selects the legacy file backend for rollback. Charts, logs,
and derived calculation files are disposable and are never authoritative.

## Subsystems

- **Pipeline:** `pipeline/`, `data_acquisition.py`, and `session.py` acquire and
  normalize provider data and build candle-close events.
- **Runtime:** `runtime/market_bus.py` fans events out to strategies;
  `options_strategy_runner.py` translates strategy intents into order actions.
- **Options:** `options/` handles quotes, contract selection, execution,
  positions, and the trade-event ledger.
- **Strategies:** `strategies/options/` contains explicitly implemented
  strategies and shared types/exit rules.
- **Indicators and objects:** `indicators/`, `objects.py`, and `storage/objects/`
  maintain strategy/chart inputs.
- **Storage:** `storage/` owns local Parquet reads/writes and viewport queries.
- **Frontend:** `web_dash/` renders charts and handles refresh notifications.
- **Integrations:** Discord and economic-calendar code currently live under
  `integrations/`. Discord will later move behind discord-hub's HTTP contract.
- **Orchestration:** `main.py` still owns lifecycle and scheduling. Generic
  lifecycle concerns will later move to automation-harness.

## Change boundaries

Do not combine storage cutover, Discord migration, harness adoption, and VPS
enablement into one unverifiable change. Each needs offline tests and its own
rollback path. See `docs/roadmap.md` and the P2f session prompt.
