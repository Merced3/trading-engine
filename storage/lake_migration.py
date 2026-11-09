"""Offline-testable Parquet → R2 migration and verification helpers."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import duckdb
import pyarrow.parquet as pq


@dataclass(frozen=True)
class ManifestEntry:
    dataset: str
    source_path: str
    object_key: str
    quality: str
    symbol: str | None
    timeframe: str | None
    range_start: str | None
    range_end: str | None
    rows: int
    byte_size: int
    sha256: str
    compression: str
    record_type: str = field(default="file", init=False)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RejectedFile:
    source_path: str
    byte_size: int
    reason: str
    record_type: str = field(default="rejection", init=False)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class R2Settings:
    account_id: str
    access_key_id: str
    secret_access_key: str = field(repr=False)
    bucket: str = "trading-data"
    prefix: str = "v1"

    @classmethod
    def from_env(cls) -> "R2Settings":
        values = {
            "account_id": os.getenv("TRADING_R2_ACCOUNT_ID"),
            "access_key_id": os.getenv("TRADING_R2_ACCESS_KEY_ID"),
            "secret_access_key": os.getenv("TRADING_R2_SECRET_ACCESS_KEY"),
        }
        missing = [f"TRADING_R2_{key.upper()}" for key, value in values.items() if not value]
        if missing:
            raise RuntimeError(f"Missing R2 settings: {', '.join(missing)}")
        bucket = os.getenv("TRADING_R2_BUCKET")
        if not bucket:
            raise RuntimeError("Missing R2 setting: TRADING_R2_BUCKET")
        return cls(
            account_id=values["account_id"],
            access_key_id=values["access_key_id"],
            secret_access_key=values["secret_access_key"],
            bucket=bucket,
            prefix=os.getenv("TRADING_R2_PREFIX", "v1").strip("/"),
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _scan_stats(connection: duckdb.DuckDBPyConnection, path: Path) -> dict[str, Any]:
    source = path.as_posix()
    columns = {
        row[0]
        for row in connection.execute(
            "describe select * from read_parquet(?, union_by_name=true)", [source]
        ).fetchall()
    }
    timestamp = "ts_iso" if "ts_iso" in columns else "ts" if "ts" in columns else None
    selections = ["count(*)"]
    if timestamp:
        selections.extend(
            [f"min(cast({timestamp} as varchar))", f"max(cast({timestamp} as varchar))"]
        )
    else:
        selections.extend(["null", "null"])
    if "symbol" in columns:
        selections.extend(["min(cast(symbol as varchar))", "max(cast(symbol as varchar))"])
    else:
        selections.extend(["null", "null"])
    row = connection.execute(
        f"select {', '.join(selections)} from read_parquet(?, union_by_name=true)", [source]
    ).fetchone()
    if row[3] is not None and row[3] != row[4]:
        raise ValueError(f"multiple symbols in one source file: {row[3]!r}, {row[4]!r}")
    return {
        "rows": row[0],
        "range_start": _iso(row[1]),
        "range_end": _iso(row[2]),
        "symbol": row[3],
    }


def _object_key(path: Path, storage_dir: Path, prefix: str, stats: dict[str, Any]) -> tuple[str, str]:
    relative = path.relative_to(storage_dir)
    parts = relative.parts
    if parts[0] == "data":
        timeframe = parts[1].lower()
        symbol = (stats["symbol"] or "UNKNOWN").upper()
        date_part = path.name[:10]
        year, month = date_part[:4], date_part[5:7]
        key = (
            f"{prefix}/market/symbol={symbol}/timeframe={timeframe}/"
            f"year={year}/month={month}/{path.name}"
        )
        return "market", key
    if parts[:2] == ("objects", "timeline"):
        year, month = parts[2].split("-", 1)
        return "objects_timeline", f"{prefix}/objects/timeline/year={year}/month={month}/{path.name}"
    if parts[:2] == ("objects", "current"):
        return "objects_current", f"{prefix}/objects/current/snapshot.parquet"
    raise ValueError(f"unsupported Parquet source layout: {relative}")


def build_inventory(
    storage_dir: Path,
    *,
    r2_prefix: str = "v1",
) -> tuple[list[ManifestEntry], list[RejectedFile]]:
    """Read every Parquet source; never mutate the source files."""
    storage_dir = storage_dir.resolve()
    project_root = storage_dir.parent
    prefix = r2_prefix.strip("/")
    if not prefix:
        raise ValueError("R2 prefix must not be empty")
    entries: list[ManifestEntry] = []
    rejected: list[RejectedFile] = []
    connection = duckdb.connect()
    try:
        candidates = [*storage_dir.joinpath("data").rglob("*.parquet")]
        candidates += storage_dir.joinpath("objects").rglob("*.parquet")
        for path in sorted(candidates):
            source_path = path.relative_to(project_root).as_posix()
            try:
                metadata = pq.ParquetFile(path).metadata
                stats = _scan_stats(connection, path)
                dataset, object_key = _object_key(path, storage_dir, prefix, stats)
            except Exception as exc:
                rejected.append(
                    RejectedFile(source_path, path.stat().st_size, str(exc).splitlines()[0])
                )
                continue
            timeframe = path.relative_to(storage_dir).parts[1].lower() if dataset == "market" else None
            quality = "snapshot" if dataset == "objects_current" else (
                "faulty" if path.stem.endswith("-faulty") else "clean"
            )
            compression = {
                metadata.row_group(group).column(column).compression
                for group in range(metadata.num_row_groups)
                for column in range(metadata.row_group(group).num_columns)
            }
            entries.append(
                ManifestEntry(
                    dataset=dataset,
                    source_path=source_path,
                    object_key=object_key,
                    quality=quality,
                    symbol=stats["symbol"],
                    timeframe=timeframe,
                    range_start=stats["range_start"],
                    range_end=stats["range_end"],
                    rows=stats["rows"],
                    byte_size=path.stat().st_size,
                    sha256=sha256_file(path),
                    compression=",".join(sorted(compression)),
                )
            )
    finally:
        connection.close()
    return entries, rejected


def write_manifest(
    output_path: Path,
    entries: Iterable[ManifestEntry],
    rejected: Iterable[RejectedFile],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for item in [*entries, *rejected]:
            handle.write(json.dumps(item.to_dict(), sort_keys=True) + "\n")


def read_manifest(path: Path) -> tuple[list[ManifestEntry], list[RejectedFile]]:
    entries: list[ManifestEntry] = []
    rejected: list[RejectedFile] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            record_type = row.pop("record_type")
            if record_type == "file":
                entries.append(ManifestEntry(**row))
            elif record_type == "rejection":
                rejected.append(RejectedFile(**row))
            else:
                raise ValueError(f"unknown manifest record type: {record_type}")
    return entries, rejected


def build_r2_client(settings: R2Settings):
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key,
        region_name="auto",
    )


def _missing_object(exc: Exception) -> bool:
    response = getattr(exc, "response", {})
    code = str(response.get("Error", {}).get("Code", ""))
    return code in {"404", "NoSuchKey", "NotFound"}


def upload_entries(
    entries: Iterable[ManifestEntry],
    *,
    project_root: Path,
    client: Any,
    bucket: str,
    on_verified: Any = None,
) -> list[dict[str, Any]]:
    """Upload idempotently and verify each remote size + source SHA metadata."""
    reports: list[dict[str, Any]] = []
    for entry in entries:
        path = project_root / entry.source_path
        if sha256_file(path) != entry.sha256:
            raise RuntimeError(f"source changed since manifest: {entry.source_path}")
        status = "uploaded"
        try:
            head = client.head_object(Bucket=bucket, Key=entry.object_key)
            if (
                head.get("ContentLength") != entry.byte_size
                or head.get("Metadata", {}).get("sha256") != entry.sha256
            ):
                raise RuntimeError(f"remote object conflicts with manifest: {entry.object_key}")
            status = "already_verified"
        except Exception as exc:
            if not _missing_object(exc):
                raise
            client.put_object(
                Bucket=bucket,
                Key=entry.object_key,
                Body=path.read_bytes(),
                ContentType="application/vnd.apache.parquet",
                Metadata={"sha256": entry.sha256, "source_path": entry.source_path},
            )
        head = client.head_object(Bucket=bucket, Key=entry.object_key)
        if (
            head.get("ContentLength") != entry.byte_size
            or head.get("Metadata", {}).get("sha256") != entry.sha256
        ):
            raise RuntimeError(f"remote verification failed: {entry.object_key}")
        if on_verified:
            on_verified(entry, bucket)
        reports.append(
            {
                "object_key": entry.object_key,
                "status": status,
                "byte_size": entry.byte_size,
                "sha256": entry.sha256,
                "verified_at": datetime.now(UTC).isoformat(),
            }
        )
    return reports


def configure_duckdb_r2(connection: duckdb.DuckDBPyConnection, settings: R2Settings) -> None:
    def literal(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    connection.execute("INSTALL httpfs")
    connection.execute("LOAD httpfs")
    # Explicit S3/path-style configuration is reliable across DuckDB versions;
    # the TYPE R2 shortcut produced incorrect 404 paths in DuckDB 1.5.6.
    connection.execute(
        "CREATE OR REPLACE SECRET trading_r2 ("
        "TYPE S3, "
        f"KEY_ID {literal(settings.access_key_id)}, "
        f"SECRET {literal(settings.secret_access_key)}, "
        "REGION 'auto', "
        f"ENDPOINT {literal(settings.account_id + '.r2.cloudflarestorage.com')}, "
        "URL_STYLE 'path', USE_SSL true)"
    )


def verify_remote_rows(
    entries: Iterable[ManifestEntry],
    *,
    connection: duckdb.DuckDBPyConnection,
    bucket: str,
) -> dict[str, int]:
    """Read remote Parquet in grouped queries and reconcile rows per object key."""
    expected = {f"s3://{bucket}/{entry.object_key}": entry.rows for entry in entries}
    if not expected:
        return {"files": 0, "rows": 0}
    observed = dict(
        connection.execute(
            "select filename, count(*) from read_parquet(?, filename=true, "
            "union_by_name=true) group by filename",
            [list(expected)],
        ).fetchall()
    )
    missing = sorted(set(expected) - set(observed))
    mismatched = sorted(
        f"{key}: expected={expected[key]} actual={observed[key]}"
        for key in set(expected) & set(observed)
        if expected[key] != observed[key]
    )
    if missing or mismatched:
        details = [*missing, *mismatched]
        raise RuntimeError("remote row reconciliation failed: " + "; ".join(details[:20]))
    return {"files": len(expected), "rows": sum(expected.values())}
