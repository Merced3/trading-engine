# Roadmap

This roadmap lists concrete migration work, not aspirational trading features.

## Now: standalone, reproducible repository

- Connect the working tree to the existing StratForge Git history.
- Rename the project and documentation to Trading Engine.
- Replace the computer-specific `venv/` with a reproducible `.venv` install.
- Add `pyproject.toml`, pytest, Ruff, Postgres/Alembic extras, and modern CI.
- Remove autonomous research/strategy-discovery code while retaining explicit
  multi-timeframe strategies and trade analytics.
- Establish a clean offline test baseline.

## Completed: durable remote data

Follow `Automations/ops/session-prompts/platform/P2f-trading-data-lake.md`:

1. Inventoried and reviewed the R2/Postgres design.
2. Uploaded 3,372 valid Parquet files with per-file checksums and remote row-count
   reconciliation (122,196 rows); two invalid placeholders were rejected.
3. Queried R2 through DuckDB and compared one 195-row Postgres-loaded slice.
4. Cut over candles/objects, trade events, config, and durable JSON state behind
   `TRADING_STORAGE_BACKEND=r2`; verified actual remote reads and idempotent
   writes. The rollback backend is `local`.
5. Kept local history only as deletion-gated rollback evidence. Derived caches,
   charts, and logs are disposable, never authoritative.

Normalized run/order/signal projections can be added when their query needs are
concrete; the raw trade-event record and strategy analytics are already remote.

## After storage: service deployment

- Adopt automation-harness for lifecycle, locking, recovery, and status.
- Replace the direct Discord bot with discord-hub HTTP transport.
- Move secrets from `cred.py` to environment-based deployment configuration.
- Add a VPS service definition, health checks, logging, backup/restore runbooks,
  and a rollback procedure.
- Size the VPS from measured runtime and query requirements.
- Keep Dash as a local diagnostic UI initially. Add private, engine-owned read
  APIs for charts/runs/positions/strategy analytics so a possible future
  personal-website frontend can consume them without data-store credentials or
  trading logic. The website itself is optional and not a deployment blocker.

## Dedicated follow-up sessions

- `docs/session-prompts/runtime-harness-migration.md`
- `docs/session-prompts/discord-hub-migration.md`
- `docs/session-prompts/frontend-api-extraction.md`
- `docs/session-prompts/vps-deployment.md`

## Explicitly out of scope

- Autonomous strategy discovery or generation inside Trading Engine. A distant
  future research-engine integration may submit reviewed strategy proposals,
  but it must never bypass this repository's explicit registry and test gates.
- Self-learning claims without a separately reviewed requirement and evidence.
- Real-money enablement as a side effect of refactoring or deployment.
