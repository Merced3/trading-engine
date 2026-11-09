# Documentation map

These documents describe the current system and its near-term operational work.
Historical ADRs remain useful as decision records even when their implementation
has since changed.

## Start here

- [Purpose and boundaries](overview/trading-engine.md)
- [Architecture map](architecture/overview.md)
- [Roadmap](roadmap.md)
- [Architecture critique (2026-11-09)](reviews/2026-11-09-architecture-critique.md)
- [Project structure](setup/project-structure.md)

## Runtime

- [Options subsystem](architecture/options-subsystem.md)
- [Engine overview](architecture/engine-overview.md)
- [Orders and tracking](architecture/orders-and-tracking.md)
- [Strategy guide](strategies/README.md)
- [Symbol and timeframe configuration](configuration/ticker-and-timeframes.md)
- [Options and reporting configuration](configuration/options-and-reporting.md)

## Data and analytics

- [Current storage system](data/storage-system.md)
- [Proposed remote storage design](data/remote-storage-design.md) — awaiting approval
- [Candle schema](data/candles_schema.md)
- [Object schema](data/objects_schema.md)
- [EMA state](data/emas.md)
- [Markers](data/markers.md)
- [Storage viewport API](api/storage-viewport.md)

## Frontend and operations

- [Frontend architecture](architecture/frontend-overview.md)
- [Dashboard stack](runbooks/dashboard-stack.md)
- [Data pipeline](runbooks/data-pipeline.md)
- [End-of-day compaction](runbooks/end-of-day-compaction.md)
- [Parquet → R2 migration](runbooks/parquet-r2-migration.md)
- [Rebuild EMA state](runbooks/rebuild-ema-state.md)
- [Storage tests](testing/storage_tests.md)

## Dedicated follow-up sessions

- [Automation-harness lifecycle](session-prompts/runtime-harness-migration.md)
- [Discord-hub transport](session-prompts/discord-hub-migration.md)
- [Frontend API / future website](session-prompts/frontend-api-extraction.md)
- [NYC3 VPS rollout](session-prompts/vps-deployment.md)

## Decisions

- [ADR 0001: separate frontend from backend](adr/0001-separate-frontend-from-backend.md)
- [ADR 0002: Parquet appends and DuckDB reads](adr/0002-parquet-append-and-duckdb-reads.md)
- [ADR 0003: decouple pipeline from orchestrator](adr/0003-decouple-data-pipeline-from-orchestrator.md)
