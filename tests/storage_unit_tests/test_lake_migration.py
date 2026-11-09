from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from storage.lake_migration import (
    ManifestEntry,
    build_inventory,
    read_manifest,
    upload_entries,
    verify_remote_rows,
    write_manifest,
)


def _write_candles(path: Path, symbol: str = "SPY") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "symbol": [symbol, symbol],
            "timeframe": ["2M", "2M"],
            "ts": [1_000, 2_000],
            "ts_iso": ["2025-09-02T13:30:00Z", "2025-09-02T13:32:00Z"],
            "open": [1.0, 2.0],
            "high": [2.0, 3.0],
            "low": [0.5, 1.5],
            "close": [1.5, 2.5],
            "volume": [10.0, 20.0],
        }
    ).to_parquet(path, index=False, compression="snappy")


def test_inventory_keys_checksums_quality_and_round_trip(tmp_path):
    storage = tmp_path / "storage"
    clean = storage / "data" / "2m" / "2025-09-02.parquet"
    faulty = storage / "data" / "2m" / "2025-09-03-faulty.parquet"
    invalid = storage / "data" / "2m" / "2025-09-04-missing.parquet"
    current = storage / "objects" / "current" / "objects.parquet"
    _write_candles(clean)
    _write_candles(faulty)
    _write_candles(current)
    invalid.parent.mkdir(parents=True, exist_ok=True)
    invalid.touch()

    entries, rejected = build_inventory(storage)
    assert len(entries) == 3
    assert len(rejected) == 1
    assert rejected[0].source_path.endswith("2025-09-04-missing.parquet")

    clean_entry = next(entry for entry in entries if entry.quality == "clean")
    assert clean_entry.object_key == (
        "v1/market/symbol=SPY/timeframe=2m/year=2025/month=09/2025-09-02.parquet"
    )
    assert clean_entry.rows == 2
    assert clean_entry.range_start == "2025-09-02T13:30:00Z"
    assert clean_entry.range_end == "2025-09-02T13:32:00Z"
    assert clean_entry.timeframe == "2m"
    assert len(clean_entry.sha256) == 64
    assert clean_entry.compression == "SNAPPY"
    assert next(entry for entry in entries if entry.quality == "faulty")
    assert next(entry for entry in entries if entry.quality == "snapshot").object_key == (
        "v1/objects/current/snapshot.parquet"
    )

    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest, entries, rejected)
    loaded_entries, loaded_rejected = read_manifest(manifest)
    assert loaded_entries == entries
    assert loaded_rejected == rejected
    assert json.loads(manifest.read_text().splitlines()[0])["record_type"] == "file"


class _MissingObject(Exception):
    def __init__(self):
        self.response = {"Error": {"Code": "404"}}


class _FakeS3:
    def __init__(self):
        self.objects = {}

    def head_object(self, *, Bucket, Key):
        try:
            return self.objects[Key]
        except KeyError:
            raise _MissingObject() from None

    def put_object(self, *, Bucket, Key, Body, ContentType, Metadata):
        self.objects[Key] = {
            "ContentLength": len(Body),
            "Metadata": Metadata,
            "Body": Body,
        }


def _entry(tmp_path: Path) -> ManifestEntry:
    storage = tmp_path / "storage"
    path = storage / "data" / "2m" / "2025-09-02.parquet"
    _write_candles(path)
    entries, rejected = build_inventory(storage)
    assert not rejected
    return entries[0]


def test_upload_is_idempotent_and_verifies_remote_metadata(tmp_path):
    entry = _entry(tmp_path)
    client = _FakeS3()
    verified = []
    kwargs = {
        "project_root": tmp_path,
        "client": client,
        "bucket": "trading-test",
        "on_verified": lambda item, bucket: verified.append((item, bucket)),
    }

    first = upload_entries([entry], **kwargs)
    second = upload_entries([entry], **kwargs)

    assert first[0]["status"] == "uploaded"
    assert second[0]["status"] == "already_verified"
    assert verified == [(entry, "trading-test"), (entry, "trading-test")]


def test_upload_rejects_source_changed_after_manifest(tmp_path):
    entry = _entry(tmp_path)
    (tmp_path / entry.source_path).write_bytes(b"changed")

    with pytest.raises(RuntimeError, match="source changed"):
        upload_entries(
            [entry], project_root=tmp_path, client=_FakeS3(), bucket="trading-test"
        )


class _FakeVerificationConnection:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, _query, params):
        urls = params[0]
        return self


def test_remote_row_reconciliation(tmp_path):
    entry = _entry(tmp_path)

    class Connection:
        def execute(self, _query, params):
            url = params[0][0]
            return type("Result", (), {"fetchall": lambda _self: [(url, entry.rows)]})()

    assert verify_remote_rows([entry], connection=Connection(), bucket="trading-test") == {
        "files": 1,
        "rows": 2,
    }

    class BadConnection:
        def execute(self, _query, params):
            url = params[0][0]
            return type("Result", (), {"fetchall": lambda _self: [(url, 1)]})()

    with pytest.raises(RuntimeError, match="expected=2 actual=1"):
        verify_remote_rows([entry], connection=BadConnection(), bucket="trading-test")
