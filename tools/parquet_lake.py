"""Inventory, upload, and verify the trading Parquet data lake.

Examples (run from the repository root):
  python tools/parquet_lake.py inventory
  alembic upgrade head
  python tools/parquet_lake.py upload --with-catalog
  python tools/parquet_lake.py verify

Live commands require the variables documented in .env.example. Inventory is
fully local and never requires credentials.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
from dotenv import load_dotenv

from storage.lake_migration import (
    R2Settings,
    build_inventory,
    build_r2_client,
    configure_duckdb_r2,
    read_manifest,
    upload_entries,
    verify_remote_rows,
    write_manifest,
)


def _inventory(args: argparse.Namespace) -> int:
    entries, rejected = build_inventory(args.storage, r2_prefix=args.r2_prefix)
    write_manifest(args.manifest, entries, rejected)
    print(
        f"[INVENTORY] files={len(entries)} rows={sum(e.rows for e in entries)} "
        f"bytes={sum(e.byte_size for e in entries)} rejected={len(rejected)}"
    )
    print(f"[INVENTORY] manifest={args.manifest}")
    for rejection in rejected:
        print(f"[REJECTED] {rejection.source_path}: {rejection.reason}")
    return 0


def _upload(args: argparse.Namespace) -> int:
    entries, rejected = read_manifest(args.manifest)
    settings = R2Settings.from_env()
    client = build_r2_client(settings)
    if args.with_catalog:
        from storage.catalog import PostgresCatalog

        catalog = PostgresCatalog.from_env()
    else:
        catalog = None
    try:
        if catalog:
            for rejection in rejected:
                catalog.record_rejection(rejection)
        reports = upload_entries(
            entries,
            project_root=args.project_root,
            client=client,
            bucket=settings.bucket,
        )
        if catalog:
            catalog.record_files(entries, settings.bucket)
    finally:
        if catalog:
            catalog.close()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", encoding="utf-8") as handle:
        for report in reports:
            handle.write(json.dumps(report, sort_keys=True) + "\n")
    print(f"[UPLOAD] verified={len(reports)} report={args.report}")
    print("[UPLOAD] Next: run the verify command to read row counts back through DuckDB.")
    return 0


def _verify(args: argparse.Namespace) -> int:
    entries, _ = read_manifest(args.manifest)
    settings = R2Settings.from_env()
    connection = duckdb.connect()
    try:
        configure_duckdb_r2(connection, settings)
        result = verify_remote_rows(entries, connection=connection, bucket=settings.bucket)
    finally:
        connection.close()
    print(f"[VERIFY] remote Parquet reconciled: files={result['files']} rows={result['rows']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.set_defaults(
        manifest=Path("artifacts/parquet-manifest.jsonl"),
        project_root=Path.cwd(),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="Build a local checksummed manifest")
    inventory.add_argument("--storage", type=Path, default=Path("storage"))
    inventory.add_argument("--r2-prefix", default="v1")
    inventory.add_argument("--manifest", type=Path)
    inventory.set_defaults(handler=_inventory)

    upload = subparsers.add_parser("upload", help="Upload and verify checksums/sizes")
    upload.add_argument("--manifest", type=Path)
    upload.add_argument("--project-root", type=Path)
    upload.add_argument("--report", type=Path, default=Path("artifacts/r2-upload-report.jsonl"))
    upload.add_argument("--with-catalog", action="store_true")
    upload.set_defaults(handler=_upload)

    verify = subparsers.add_parser("verify", help="Read remote Parquet and reconcile row counts")
    verify.add_argument("--manifest", type=Path)
    verify.set_defaults(handler=_verify)

    args = parser.parse_args()
    if getattr(args, "project_root", None) is None:
        args.project_root = Path.cwd()
    # Actual process env wins, then project overrides, then shared ops secrets.
    load_dotenv(args.project_root / ".env")
    ops_env = args.project_root.parent.parent / "ops" / "env"
    load_dotenv(ops_env / "r2.env")
    load_dotenv(ops_env / "data-platform.env")
    if args.manifest is None:
        args.manifest = Path("artifacts/parquet-manifest.jsonl")
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
