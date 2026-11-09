# Proposed remote storage design — review required

Status: **implemented and verified**. Initial upload, remote reads/writes,
trade-event migration, and runtime config/state cutover are complete. Local
source files remain rollback evidence under the deletion gate. See P2f Session
Progress for counts, acceptance checks, and the DuckDB/Postgres benchmark.

## Why two systems

Parquet is columnar: analytical queries can read only the columns and row groups
they need. R2 is S3-compatible object storage for durable files, not a relational
database. DuckDB can query those files remotely without downloading the whole
dataset.

Postgres is the system of record for structured operational data and the file
catalog. It is not the default destination for every candle: putting all market
history in row-oriented Postgres would make analytical scans and retention more
expensive without improving the engine's access pattern.

## Source inventory

| Dataset | Readable files | Rows | Size | Observed range (UTC) |
| --- | ---: | ---: | ---: | --- |
| 2m candles | 274 | 52,707 | 3.31 MiB | 2025-09-02 to 2026-10-13 |
| 5m candles | 274 | 21,073 | 2.26 MiB | 2025-09-02 to 2026-10-13 |
| 15m candles | 1,438 | 37,268 | 9.80 MiB | 2021-01-04 to 2026-10-02 |
| Object timeline | 1,385 | 10,894 | 11.98 MiB | 2021-03-21 to 2026-10-01 |
| Current objects | 1 | 254 | 0.01 MiB | snapshot |
| **Total** | **3,372** | **122,196** | **27.36 MiB** | |

Two additional zero-byte files, `2m/2026-02-19-missing.parquet` and
`5m/2026-02-19-missing.parquet`, are invalid Parquet placeholders. Exclude them
from the valid upload and record them in a rejected-file report. Thirteen
readable `*-faulty.parquet` files remain separate and retain their `faulty`
quality label; do not merge them into clean dayfiles.

## R2 layout

Use one versioned prefix so a failed migration cannot overwrite a later schema:

```text
v1/
  market/symbol=SPY/timeframe=2m/year=2025/month=09/2025-09-02.parquet
  market/symbol=SPY/timeframe=5m/year=2025/month=09/2025-09-02.parquet
  market/symbol=SPY/timeframe=15m/year=2021/month=01/2021-01-04.parquet
  objects/timeline/year=2021/month=03/2021-03-21.parquet
  objects/current/snapshot.parquet
```

Hive-style `key=value` directories let DuckDB prune symbol/timeframe/date
partitions. Existing files are copied without changing values during the first
migration. This gives a direct source-to-remote verification story.

Daily files are appropriate for live appends and recovery but small at this
scale. After verification, compact clean market data by symbol/timeframe/month;
keep faulty inputs separate. Target roughly 16–64 MiB per compacted file as data
grows, using Snappy compression initially. Do not combine timeframes or sacrifice
late-arrival/idempotency handling merely to hit a file-size target.

## Postgres catalog and operational records

Create a dedicated `trading` database. Initial catalog:

- `datasets`: stable dataset name, schema version, R2 prefix, symbol/timeframe
  where applicable, and active/archived status.
- `dataset_files`: dataset ID, R2 object key, source relative path, quality
  (`clean`, `faulty`, `snapshot`), time bounds, row count, byte size, SHA-256,
  compression, upload timestamp, and verification status. Unique object key and
  checksum constraints prevent accidental duplicates.
- `migration_rejections`: source path, reason, size, and discovery timestamp for
  zero-byte or unreadable files.

Subsequent operational tables, introduced with Alembic migrations and adapter
tests:

- `runs` and `run_timeframes`;
- `strategies` and versioned `strategy_configs`;
- `signals`, `orders`, `positions`, and `position_events`;
- strategy performance as queryable views or derived snapshots, not the only
  copy of trade events.

Raw quote capture stays disabled by default. If enabled later, it belongs in a
separate R2 dataset with an explicit retention policy—not unbounded local JSONL.

## Verification and cutover

1. Hash and read every source file; write a local manifest without changing the
   source data.
2. Upload valid files, then compare remote size and SHA-256 and read row counts
   back through DuckDB.
3. Reconcile totals by dataset, quality, symbol, timeframe, and time bounds.
   Require zero unexplained differences.
4. Query R2 directly with DuckDB and run representative engine viewport queries.
5. Load one small candle slice into Postgres and compare query latency, storage,
   and operational complexity with DuckDB-on-R2. This is a learning benchmark,
   not a reason to duplicate the full dataset.
6. Add storage adapters and contract tests. Write new candles/objects to R2 and
   their catalog entries to Postgres; write operational records to Postgres.
7. Cut over reads only after parity tests pass. Keep local historical files as a
   rollback copy until the owner explicitly approves deletion.

After cutover there is no authoritative local data store. Temporary charts,
logs, and any cache are disposable and never the only copy.

## Rollback

The `v1/` prefix and local source files remain unchanged during verification. A
failed adapter test leaves the engine on its existing local backend. Runtime
updates archive the prior complete object under `v1/versions/` and catalog it in
a separate `*_versions` dataset before replacing the current object/checksum in
one catalog transaction. Version datasets are excluded from viewport reads. A
failed post-cutover run can disable remote writes and restore a prior cataloged
version; local sources remain deletion-gated rollback evidence.
