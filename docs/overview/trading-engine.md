# Trading Engine — purpose and current boundaries

Trading Engine hosts multiple explicitly implemented option strategies on one
configured underlying symbol. Strategies consume shared candle-close events on
multiple timeframes, while order management and position tracking remain shared
runtime services.

## What exists

- Provider-backed market data acquisition and 2m/5m/15m candle construction.
- Concurrent option strategies loaded from the explicit `strategies/options/`
  registry. Adding a module alone never enables it.
- Contract selection, paper execution, position actions, and end-of-day close.
- Trade-event storage and strategy performance reports.
- EMA state, markers, zones/objects, charts, and Discord notifications.
- Local Parquet candle/object storage with DuckDB query helpers.

## What does not exist

- No autonomous strategy generation, research runner, or self-learning system.
  A separate research engine may deliberately generate and propose strategies
  in the distant future, but that is a separate project/integration. Trading
  Engine must never auto-register or execute proposals without explicit review.
- No remote database or object-storage backend yet.
- No completed automation-harness lifecycle integration.
- No completed discord-hub transport integration.
- No reviewed VPS deployment or real-money rollout.

## Immediate direction

First make the standalone repository reproducible and keep the existing offline
suite healthy. Then move durable data to the reviewed Postgres/R2 design and cut
over engine reads/writes. Runtime and Discord migrations remain separate,
testable changes.

See `docs/architecture/overview.md` for the subsystem map and `docs/roadmap.md`
for current priorities.
