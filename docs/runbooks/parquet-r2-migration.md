# Runbook: Parquet → R2 + Postgres catalog

## Preconditions

- Use the project `.venv` and install `.[dev]` or `.[postgres]`.
- Create the R2 bucket and a token limited to that bucket.
- Create an empty Postgres `trading` database and a migration/login role.
- Reuse `ops/env/data-platform.env` and `ops/env/r2.env`; the CLI discovers them
  automatically. `.env.example` is only for optional project overrides. Never
  paste live credentials into Git, tickets, docs, or chat.
- For laptop Postgres work, open the ops SSH tunnel: direct 25060 → local 25432
  for Alembic and PgBouncer 25061 → local 25433 for app/catalog connections.
- Keep the engine stopped during the initial snapshot so source files cannot
  change between inventory and upload.

## 1. Local inventory (no credentials or remote calls)

```bash
python tools/parquet_lake.py inventory
```

Expected current result: 3,372 valid files, 122,196 rows, 28,683,965 bytes, and
two zero-byte rejections. The manifest is `artifacts/parquet-manifest.jsonl`;
`artifacts/` is ignored by Git and contains no source-data mutations.

## 2. Create/upgrade the Postgres catalog

```bash
alembic upgrade head
```

To inspect DDL without connecting to Postgres:

```bash
TRADING_DATABASE_URL=postgresql://user:password@localhost:5432/trading \
  alembic upgrade head --sql
```

## 3. Upload with per-file verification

```bash
python tools/parquet_lake.py upload --with-catalog
```

The command rechecks every source SHA-256 before upload, stores that checksum in
R2 metadata, reads back remote size/checksum, and upserts the verified file into
Postgres. Existing matching objects are skipped; a conflicting object stops the
command. The report is `artifacts/r2-upload-report.jsonl`.

## 4. Reconcile remote rows through DuckDB

```bash
python tools/parquet_lake.py verify
```

DuckDB reads the Parquet files directly from R2 and compares row counts for every
object key with the local manifest. Any missing object or row-count difference is
an error. Do not cut over the engine until this succeeds.

## 5. Stop before runtime cutover

### Completed initial migration evidence (2026-11-08)

- R2 and Postgres contain 3,372 verified objects/rows totaling 122,196 rows and
  28,683,965 bytes; DuckDB read every remote object and matched every row count.
- Catalog quality counts are 3,358 clean, 13 faulty, and 1 snapshot; two
  zero-byte source placeholders are recorded in `migration_rejections`.
- A 195-row 2m slice matched aggregates in DuckDB-on-R2 and a temporary Postgres
  table. Median warm query times from the laptop were 147.5 ms and 58.4 ms
  respectively; the 57,344-byte temporary table was dropped. This was diagnostic,
  not a controlled performance benchmark. Details are in ignored
  `artifacts/postgres-r2-benchmark.json`.


The upload does not change engine reads/writes. The next work is the remote query
benchmark, storage adapters, contract tests, and an explicit cutover. Keep local
source files for rollback until the owner approves their deletion.

## Rollback before cutover

No engine change is required. Remove incomplete remote objects only through a
separately reviewed cleanup command; never delete the local source to resolve an
upload failure. Re-running `upload` is safe when source and remote checksums
match.
