# Core constraints — changes requiring explicit owner review

## Trading safety

- `REAL_MONEY_ACTIVATED` stays false unless the owner explicitly approves a
  live-trading change. Paper execution is the default development path.
- Broker order submission, position closing, provider credentials, and account
  configuration are external side effects, never test fixtures.
- Multi-strategy isolation, multi-timeframe event routing, idempotent order
  handling, and end-of-day position management require regression coverage.

Guardian paths:

- `main.py`, `options/`, `runtime/`, `strategies/`, and `config.json`
- `cred-example.py` and any future environment/configuration schema

## Data and deployment safety

- Do not delete or rewrite historical `storage/` data during refactors.
- Remote storage requires an inventory, design review, verified copy, rollback
  path, and explicit cutover. Local files remain authoritative until then.
- Database schema changes require migrations and a rollback/recovery story.
- VPS deployment and real-money enablement are separate approvals.

Guardian paths:

- `paths.py`, `storage/`, `pipeline/`, database migrations, and `pyproject.toml`
- `.github/` and deployment configuration

## Rule of thumb

If a change can submit a real trade, lose the only copy of data, silently switch
storage backends, or make a deployed process unrecoverable, stop for owner
review.
