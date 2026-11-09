# Session: Trading Engine — automation-harness lifecycle

**Suggested session name:** `trading-engine: harness lifecycle`

**Gate:** P2f remote-storage cutover is verified. Do not combine this with the
initial Parquet upload or real-money enablement.

## Prompt

Adopt `automation-harness` for Trading Engine's long-running lifecycle without
changing strategy, broker, or analytics behavior. The dependency exists, but the
engine still orchestrates itself in `main.py`; do not claim integration is done
until the real entry point uses it.

1. Read the harness README/architecture and current `main.py` lifecycle.
2. Inventory process ownership: single-instance lock, startup, shutdown, market
   calendar loop, feed/options tasks, restart recovery, structured logs/status.
3. Present the mapping and stop for design review. Keep trading policy in this
   repo; generic lifecycle changes belong upstream only after a real shared need.
4. Implement offline tests first for normal shutdown, exception propagation,
   restart, stale state, and no catch-up storm. No live broker/Discord calls.
5. Wire the actual entry point and run the full suite plus a bounded paper-mode
   acceptance test. Preserve a rollback entry point until acceptance passes.
6. Document the operational contract and update P2f/roadmap references.

**Done when:** harness owns generic lifecycle, no duplicate local scheduler/lock
remains, offline tests pass, and paper runtime recovery is demonstrated.

## Session Progress
