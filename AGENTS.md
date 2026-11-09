# AGENTS.md — orientation for AI sessions

You are working in **trading-engine**, a standalone repository for a personal
multi-strategy, multi-timeframe options trading engine.

## Scope and boundaries

- Keep explicit, testable strategies and their execution/performance analytics.
- Do not add autonomous strategy generation, research agents, or self-learning
  claims. Those were intentionally removed. Executable strategies must be
  explicitly registered in `strategies/options/__init__.py`.
- Preserve multi-timeframe strategy execution and remote append/query contracts.
  R2/Postgres is current; `TRADING_STORAGE_BACKEND=local` is the rollback path.
- Treat broker, provider, Discord, and VPS operations as external side effects.
  Offline tests must not start them or require real credentials.
- `automation-harness` should eventually own generic lifecycle concerns.
  `discord-hub` should eventually own Discord transport. Do not claim either
  migration is complete merely because a dependency or setting exists.
- Remote data work follows `Automations/ops/session-prompts/platform/
  P2f-trading-data-lake.md`. Its design-review stop is intentional.

## Safety

- Never enable real-money trading, submit orders, rename a remote repository,
  push, deploy, or delete historical market/trade data without explicit owner
  approval for that action. Generated research ledgers were deleted with owner
  approval; do not recreate them.
- `cred.py`, `.env`, tokens, account numbers, and live database URLs stay out of
  Git. Tests use the credential stub in `tests/conftest.py`.
- Do not delete `storage/` during cleanup. Large raw quote/research artifacts
  require an explicit retention decision.

## Common commands

```bash
python -m pip install -e ../automation-harness
python -m pip install -e ".[dev]"
pytest
ruff check .
```

## Orientation

Read `README.md` for actual status, `docs/roadmap.md` for the next migrations,
and the module under change. `docs/` contains historical design notes; update
notes that no longer match the code instead of treating them as truth.
