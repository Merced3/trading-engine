# Trading Engine architecture critique — 2026-11-09

## Executive verdict

Trading Engine is a useful prototype with a now-verified remote data migration.
It is **not yet a trustworthy execution system**, and the 89 passing tests do not
make it one.

The old code answers yesterday's questions: how to keep a long-running personal
script alive, draw charts, append files, and make several EMA ideas place paper
trades. Today's questions are harder: whether candles are complete, fills are
real, risk is bounded, restarts are safe, failures are visible, and analytics
describe the same trades the broker actually executed.

The R2/Postgres work was worth doing. It removed disposable clutter and created
durable, queryable records. It did **not** fix the trading kernel. Do not interpret
"remote, migrated, and tested" as "production safe."

The correct response is not another total rewrite driven by enthusiasm. Preserve
the useful contracts, establish deterministic evidence, and replace the kernel in
small pieces behind replay and failure-injection gates.

## What is genuinely worth keeping

- **Explicit strategy registration.** Strategies are code, not something the
  execution engine invents. A future research engine must remain external.
- **The basic strategy boundary.** Candle-close input and explicit position
  actions are more useful than strategies directly submitting broker requests.
- **Multi-timeframe intent.** One event model shared across timeframes is a good
  requirement, although the current scheduling/delivery implementation is weak.
- **Provider/executor seams.** Quote providers and order executors are imperfect,
  but they are places to introduce better implementations without rewriting
  strategy ideas first.
- **Trade-event history and strategy reporting.** The 6,859-event migration and
  local/remote analytics parity are useful evidence. Keep and deepen the raw
  record; do not confuse current metrics with a complete performance model.
- **Migration tooling and catalog.** Checksummed manifests, remote row
  reconciliation, Alembic, and offline fakes are durable engineering assets.
- **Offline tests and CI.** They are a starting safety net, not proof of live
  correctness. Keep them while adding replay, concurrency, and failure tests.

## P0 — correctness and safety problems

### 1. Candle completeness depends on lucky message timing

**Evidence:** `pipeline/data_pipeline.py` closes a candle only while processing a
trade whose wall-clock seconds exactly match a scheduled or buffered timestamp.
`queue.get()` can also wait indefinitely after the close condition was last
checked.

**Why this matters:** a quiet symbol, provider gap, delayed packet, or process
stall can skip a candle close. A slow R2 write makes later timing less likely to
match. Strategies then trade incomplete or duplicated market state, and changing
storage latency can change trading behavior.

**Replacement:** derive candles from event timestamps and a deterministic session
clock. Close all elapsed intervals independently of whether a trade arrives at a
lucky second. Use bounded queue waits/timers, explicit late-data policy, catch-up
limits, gap metrics, and replayable provider events. A candle needs a stable
identity and close reason, not a formatted wall-clock string comparison.

### 2. Event delivery is fire-and-forget with silent loss

**Evidence:** `runtime/market_bus.py` creates untracked async tasks. Bounded queues
silently drop the oldest event. Async listener failures are not awaited or
aggregated. The options runner serializes work under one lock, so one slow
strategy can hold up later events while tasks continue accumulating.

**Why this matters:** there is no reliable answer to "did every strategy process
this candle exactly once?" Shutdown can abandon strategy, notification, and
ledger work. Backpressure changes behavior instead of producing an explicit
degraded state.

**Replacement:** use tracked workers with per-strategy queues, sequence numbers,
timeouts, cancellation, exception capture, lag metrics, and explicit overflow
policy. Drain critical work on shutdown. A strategy failure must be isolated and
visible; it must not silently block or change every other strategy.

### 3. The broker is not the system of record, and recovery is incomplete

**Evidence:** `options/order_manager.py` keeps orders/positions in memory.
`OptionsStrategyRunner` has a second in-memory position map. There is no startup
broker reconciliation or restoration of strategy position state. Real order
fill updates are not a durable, authoritative order-state machine.

**Why this matters:** a restart can forget open exposure or allow a strategy to
repeat an action. An order accepted by the broker but not recorded locally is
already ambiguous. A database full of events is not recovery unless there is a
tested projection and reconciliation with the broker.

**Replacement:** implement broker/client order IDs, durable order intents,
submission outcomes (including `UNKNOWN`), fill events, position projections,
and startup reconciliation. Reconcile broker orders/positions before enabling
signals. Test crash windows before submit, after submit before response, after
response before database commit, and during restart.

### 4. Real-money readiness is mostly an illusion

**Evidence:** `main.py` always constructs `PaperOrderExecutor`; the real-money
flag is not a complete execution implementation. `TradierOrderExecutor` submits
and fetches status, but there is no robust live order lifecycle around it.

**Why this matters:** a configuration flag can suggest a capability the system
does not have. Paper success does not demonstrate live fill handling, restart
safety, or broker reconciliation.

**Replacement:** describe live execution as **unimplemented**, not merely
"disabled." Remove the flag from normal configuration until a separately reviewed
live-execution project exists. Require explicit environment, account, strategy,
and risk acknowledgments for any future live mode.

### 5. There is no portfolio risk authority

**Evidence:** quantity is hardcoded to one in `main.py`. The strategy runner can
close/reverse based on signals, but there is no central risk decision for buying
power, aggregate exposure, correlated positions, daily loss, contract liquidity,
or order-rate limits.

**Why this matters:** six independently reasonable strategies can still create an
unreasonable portfolio. Strategy-local position limits are not portfolio risk
management.

**Replacement:** every order intent must pass a synchronous risk service before
submission. Start with maximum order count, notional, contracts per strategy and
portfolio, daily loss lockout, stale-quote rejection, spread/liquidity limits,
and kill-switch behavior. Risk decisions and reasons belong in the durable event
record.

### 6. Paper execution is too generous for evaluating weak strategies

**Evidence:** `options/execution_paper.py` fills market orders immediately at a
single current quote. Limit orders reject when not immediately marketable rather
than resting. There are no partial fills, queue position, latency, commissions,
or changing quotes.

**Why this matters:** the simulator can produce performance that a broker cannot
repeat, especially for 0DTE options with wide/fast spreads. The current negative
historical metrics are honest output from the model, not proof of tradable edge.

**Replacement:** timestamp quotes and orders, model spread/latency/fees, support
partial fills and cancellations, and run sensitivity scenarios. Compare paper
orders with a recorded market tape before trusting performance differences.

### 7. Six no-alpha strategies are enabled by default

**Evidence:** `strategies/options/__init__.py` registers six builders and
`load_strategies()` returns all of them.

**Why this matters:** explicit registration is better than discovery, but the
default is still "run everything." That is an experiment roster, not a production
deployment policy.

**Replacement:** default to **zero enabled strategies**. Deployment configuration
should name exact strategy/version/timeframe instances and their risk limits.
Keep experimental instances in paper-only runs with explicit run IDs.

## P1 — architecture problems that inflate every change

### 8. Synchronous remote persistence sits in the market hot path

**Evidence:** candle close calls the storage sink before EMA/strategy work. The R2
writer reads a dayfile, merges it, archives the prior object, writes/verifies the
replacement, and updates Postgres.

**Why this matters:** network latency now directly delays candle construction and
strategy delivery. A storage outage becomes a trading outage with ambiguous
backlog behavior.

**Replacement:** append the canonical event to a durable local/remote ingestion
queue with explicit acknowledgment semantics, then let storage and strategy
consumers progress independently. Compact R2 objects on a separate cadence.
Measure before optimizing; do not add Kafka or other infrastructure theater for
one small engine.

### 9. R2 and Postgres updates are not one atomic transaction

**Evidence:** prior-version archive, object replacement, head verification, and
catalog update are separate external operations. Concurrent writers can read the
same old dayfile and lose each other's updates.

**Why this matters:** archive/catalog drift is possible after a crash, and two
engine instances can silently lose candles.

**Replacement:** enforce one writer with the harness lease plus a per-dataset
writer ID/fencing token. Add generation numbers and recovery checks for every
failure window. Immutable generations with a Postgres current-pointer update are
cleaner than treating an overwritten object plus archive as a transaction.

### 10. Remote reads are correct but wasteful

**Evidence:** viewport file collection lists every cataloged dayfile for a
timeframe; DuckDB then receives the full list even for one day. Catalog time
bounds are text.

**Why this matters:** verification-scale data is tiny, so this passes now. It will
not age well as history grows. Text bounds also work against the platform's
`timestamptz` convention.

**Replacement:** store normalized UTC bounds as `timestamptz`, filter catalog
rows by requested date/symbol/timeframe/quality/current generation, and only then
construct the R2 read. Add bounded query benchmarks before adding caches.

### 11. Strategy, orchestration, reporting, and side effects are tangled

**Evidence:** `main.py` owns provider, options runtime, Discord, scheduling,
balance, EOD, and subprocess concerns. `objects.py` is 947 lines;
`indicators/flag_manager.py` is 681. Async notifier hooks can spawn additional
untracked work.

**Why this matters:** a small change requires understanding unrelated behavior.
Tests can prove helper functions while missing the actual production wiring.

**Replacement:** split composition from domain code. One composition root should
wire market-data, strategy workers, risk, execution, storage projections,
reporting, and lifecycle. Domain services should not start subprocesses or know
Discord. Make critical event/ledger writes part of an acknowledged workflow.

### 12. Configuration is flexible in the wrong way

**Evidence:** arbitrary JSON configuration is now in Postgres, while provider and
Discord secrets still use `cred.py`. There is no versioned, validated deployment
schema for strategy instances and risk.

**Why this matters:** a database is not a type system. Missing or misspelled values
are still runtime surprises, and mutable JSON is not a safe rollout mechanism.

**Replacement:** use environment-based service secrets and a versioned Pydantic
configuration for non-secret deployment policy. Validate symbol/timeframes,
strategy versions, risk limits, and real-money prohibition before any provider
connection. Store explicit config revision IDs on runs and events.

### 13. Time and identity contracts are inconsistent

**Evidence:** code mixes New York time, `America/Chicago`, integer milliseconds,
ISO strings, naive timestamps, and timestamptz values. Symbol-specific paths and
chart names coexist with the claim of ticker independence.

**Why this matters:** session boundaries, analytics grouping, and remote range
filters can disagree even when individual conversions look reasonable.

**Replacement:** UTC instants at every persistence/API boundary; IANA session
timezone only for session/calendar logic; one canonical event/candle identity;
SPY as configuration data, not path semantics. Add DST and early-close replay
fixtures.

## P2 — analytics, dead weight, and operability

### 14. Current analytics are useful summaries, not an evaluation framework

The existing win rate, P&L, expectancy, and per-strategy reports are worth
keeping. They do not fully answer whether a strategy is good:

- commissions/slippage and quote freshness are not first-class;
- there is no equity curve, drawdown, exposure, turnover, tail loss, or capacity;
- arbitrary sample-size labels do not establish significance;
- there is no benchmark, regime split, walk-forward split, or sensitivity run;
- positions derived from events are not yet reconciled to broker statements.

Keep the reporting surface, but build it from a tested position/fill projection.
Make "no demonstrated edge" the default conclusion.

### 15. Likely deletion/isolation candidates

Do not delete these merely because they are old; first prove whether a registered
strategy or required chart consumes them:

- the zone/flag machinery in `objects.py` and `indicators/flag_manager.py`—the
  current options runner directly consumes EMA snapshots, not those objects;
- the alternate legacy `append_object_event` schema in
  `storage/parquet_writer.py`;
- unused CSV order helpers and legacy global/shared-state fields;
- Selenium/Chrome economic-calendar scraping inside the execution process;
- the 808-line `tools/discord_test_sender.py` as a production-adjacent utility;
- generated docs and commented-out/dead branches that describe nonexistent
  systems.

Prefer removal after dependency evidence. Otherwise make each an optional,
separately owned feature with a test and a clear consumer.

### 16. Tests need to prove behavior, not just module health

The current suite is valuable but mostly offline unit/integration coverage. It
lacks a deterministic full-day golden replay, crash-window tests, concurrent
writer tests, real broker sandbox reconciliation, and quantified coverage of the
production composition root. Broad legacy Ruff exclusions also reduce the value
of "lint clean."

Add tests in this order:

1. Full-session deterministic replay with exact candle/event/order expectations.
2. Empty/quiet periods, delayed/out-of-order trades, DST, early close, reconnect.
3. Slow/failing strategy, queue overflow, shutdown drain, and restart recovery.
4. Broker timeout/unknown submission, partial fills, duplicate/out-of-order fills.
5. R2/Postgres failure windows and two-writer fencing.
6. Paper-vs-recorded-tape execution comparison and analytics golden datasets.

## Target architecture — smaller, not grander

```text
Provider events (recorded, timestamped, replayable)
        │
        ▼
Deterministic candle builder ──────► canonical event journal
        │                                  │
        ▼                                  ├──► R2 compaction + catalog projection
Strategy workers (isolated queues)         ├──► strategy analytics projection
        │                                  └──► read API / diagnostic UI
        ▼
Order intents ──► portfolio risk authority
                          │
                          ▼
                Durable order state machine
                          │
                          ▼
                    Broker executor
                          │
                          ▼
               Fills + broker reconciliation
```

Key rules:

- The broker is authoritative for external execution; the event journal is the
  authoritative record of what the engine intended and observed.
- Strategies propose; risk disposes; executors never invent strategy meaning.
- No strategy directly writes charts, Discord, Postgres, or broker requests.
- Every event has IDs, UTC timestamps, run/config versions, and idempotency keys.
- Projections are rebuildable. Analytics are derived, not a second incompatible
  source of truth.
- Start with simple Postgres/queue implementations and measured requirements.
  Do not add a distributed platform to solve a one-process problem.

## Incremental replacement plan

### Gate A — freeze evidence, not development

- Record representative provider streams and the current full-session outputs.
- Build a deterministic replay harness and a small set of golden trading days.
- Mark live execution unimplemented and default the enabled strategy roster to
  empty.
- Document which old subsystems have actual consumers.

**Exit:** the same input produces explicit, reviewable baseline output; no hidden
provider, broker, Discord, R2, or Postgres calls are needed.

### Gate B — replace market-time and delivery semantics

- Implement deterministic candle closes and tracked strategy workers.
- Add gap/late/overflow policies and metrics.
- Prove replay, slow-listener, shutdown, and reconnect behavior.

**Exit:** candle/event sequences are complete and deterministic under faults;
storage latency cannot change the candle schedule.

### Gate C — make execution recoverable

- Add order intents, client IDs, fills, durable projections, risk checks, and
  broker reconciliation.
- Improve paper execution and compare it with recorded tapes.
- Restore strategy/runtime state before signals are enabled.

**Exit:** every crash-window and partial-fill test passes; startup cannot duplicate
an order or forget known exposure.

### Gate D — simplify and remove

- Move composition out of `main.py`; validate versioned deployment config.
- Remove or isolate unused flag/zone/CSV/shared-state paths.
- Move calendar retrieval and Discord behind their appropriate adapters/services.
- Tighten lint rules module by module.

**Exit:** each remaining subsystem has a consumer, contract, and failure owner.

### Gate E — optimize measured remote data paths

- Prune catalog reads by normalized UTC bounds and current generation.
- Separate ingestion from R2 compaction; add writer fencing/generation recovery.
- Keep analytics and the future website on read projections/APIs.

**Exit:** remote failure tests pass and measured query/write latency meets the
engine's actual budget.

## Final recommendation

Do **not** rewrite the whole engine from scratch, and do **not** spend the next
month polishing R2. The most valuable existing asset is not the old orchestration;
it is the collection of explicit contracts, historical events, migration tools,
and tests that let us measure replacements.

Build the deterministic replay harness first. It will tell us which behavior is
intentional, which is accidental, and which old code can finally be deleted
without guessing. Until then, this is a useful research/execution prototype with
remote storage—not a production trading engine.
