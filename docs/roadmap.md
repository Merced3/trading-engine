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

## Next: durable remote data

Follow `Automations/ops/session-prompts/platform/P2f-trading-data-lake.md`:

1. Finish the read/write inventory and present the R2/Postgres design for review.
2. Upload existing Parquet with row-count and checksum verification.
3. Query R2 Parquet remotely with DuckDB; compare one Postgres-loaded slice.
4. Add storage adapters and tests, then explicitly cut over engine reads/writes.
5. Keep a disposable local cache only where it has a measured purpose.

Historical data must not be deleted as part of the initial upload.

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
