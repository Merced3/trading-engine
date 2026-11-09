from __future__ import annotations

import importlib

import pandas as pd

from storage.lake_migration import R2Settings
from storage.remote import RemoteStore


class _MissingObject(Exception):
    def __init__(self):
        self.response = {"Error": {"Code": "404"}}


class _FakeS3:
    def __init__(self):
        self.objects = {}

    def get_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise _MissingObject()
        return {"Body": type("Body", (), {"read": lambda _self: self.objects[Key]["Body"]})()}

    def put_object(self, *, Bucket, Key, Body, ContentType, Metadata):
        self.objects[Key] = {
            "Body": Body,
            "ContentLength": len(Body),
            "Metadata": Metadata,
        }

    def head_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise _MissingObject()
        return self.objects[Key]

    def copy_object(self, *, Bucket, Key, CopySource, MetadataDirective):
        self.objects[Key] = dict(self.objects[CopySource["Key"]])


class _EmptyResult:
    def fetchall(self):
        return []


class _FakeConnection:
    def execute(self, *_args):
        return _EmptyResult()


class _FakeCatalog:
    def __init__(self):
        self.connection = _FakeConnection()
        self.entries = []

    def record_files(self, entries, bucket):
        self.entries.extend((entry, bucket) for entry in entries)


def _store():
    settings = R2Settings(
        account_id="test-account",
        access_key_id="test-key",
        secret_access_key="test-secret",
        bucket="test-bucket",
    )
    return RemoteStore(settings=settings, client=_FakeS3(), catalog=_FakeCatalog())


def _candle(ts: int, close: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "SPY",
                "timeframe": "15m",
                "ts": ts,
                "ts_iso": pd.to_datetime(ts, unit="ms", utc=True).isoformat(),
                "open": close,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": 10.0,
            }
        ]
    )


def test_remote_candle_append_is_sorted_and_idempotent():
    store = _store()
    first = _candle(1_756_810_800_000, 100.0)
    second = _candle(1_756_809_900_000, 99.0)

    first_entry = store.append_candle("SPY", "15m", first)
    store.append_candle("SPY", "15m", second)
    store.append_candle("SPY", "15m", _candle(1_756_810_800_000, 101.0))

    result = store.read_dataframe(first_entry.object_key)
    assert len(result) == 2
    assert result["ts"].is_monotonic_increasing
    assert result.loc[result["ts"] == 1_756_810_800_000, "close"].iloc[0] == 101.0
    assert result["global_x"].tolist() == [0, 1]
    assert first_entry.rows == 1
    assert store.catalog.entries[-1][0].rows == 2
    version_entries = [item for item in store.catalog.entries if item[0].dataset == "market_versions"]
    assert len(version_entries) == 2
    assert all(item[0].object_key.startswith("v1/versions/") for item in version_entries)
    assert store.catalog.entries[-1][0].sha256 == store.client.objects[first_entry.object_key][
        "Metadata"
    ]["sha256"]


def test_remote_snapshot_round_trip():
    store = _store()
    frame = pd.DataFrame([{"id": "zone-1", "status": "active"}])
    entry = store.write_dataframe(
        key=store.current_objects_key(),
        frame=frame,
        dataset="objects_current",
        source_path="storage/objects/current/objects.parquet",
        quality="snapshot",
    )

    result = store.read_dataframe(entry.object_key)
    pd.testing.assert_frame_equal(result, frame)


def test_parquet_writer_uses_remote_without_creating_local_data(tmp_path, monkeypatch):
    store = _store()
    monkeypatch.setenv("TRADING_STORAGE_BACKEND", "r2")
    monkeypatch.setattr("storage.remote.get_remote_store", lambda: store)
    writer = importlib.import_module("storage.parquet_writer")

    writer.append_candle(
        "SPY",
        "15m",
        {
            "timestamp": "2025-09-02T09:45:00-04:00",
            "open": 1,
            "high": 2,
            "low": 0.5,
            "close": 1.5,
            "volume": 1000,
        },
    )

    assert store.catalog.entries
    assert not list(tmp_path.rglob("*.parquet"))
