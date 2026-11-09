"""Runtime R2/Postgres storage, selected explicitly with TRADING_STORAGE_BACKEND=r2."""

from __future__ import annotations

import hashlib
import io
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
from dotenv import load_dotenv

from storage.catalog import PostgresCatalog
from storage.lake_migration import ManifestEntry, R2Settings, build_r2_client, configure_duckdb_r2


@lru_cache(maxsize=1)
def load_runtime_environment() -> None:
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")
    ops_env = project_root.parent.parent / "ops" / "env"
    load_dotenv(ops_env / "r2.env")
    load_dotenv(ops_env / "data-platform.env")


def remote_enabled() -> bool:
    load_runtime_environment()
    return os.getenv("TRADING_STORAGE_BACKEND", "local").strip().lower() == "r2"


class RemoteStore:
    def __init__(
        self,
        *,
        settings: R2Settings | None = None,
        client: Any = None,
        catalog: Any = None,
    ) -> None:
        self.settings = settings or R2Settings.from_env()
        self.client = client or build_r2_client(self.settings)
        self.catalog = catalog or PostgresCatalog.from_env()

    def configure_duckdb(self, connection: duckdb.DuckDBPyConnection) -> None:
        configure_duckdb_r2(connection, self.settings)

    def list_candle_urls(self, timeframe: str, symbol: str | None = None) -> list[str]:
        sql = """
            select object_key from dataset_files
            where dataset_id = (select id from datasets where name = 'market')
              and verification_status = 'verified'
              and lower(timeframe) = %s
        """
        params: list[Any] = [timeframe.lower()]
        if symbol:
            sql += " and symbol = %s"
            params.append(symbol.upper())
        sql += " order by object_key"
        keys = self.catalog.connection.execute(sql, params).fetchall()
        return [f"s3://{self.settings.bucket}/{row[0]}" for row in keys]

    def list_dataset_keys(self, dataset: str) -> list[str]:
        rows = self.catalog.connection.execute(
            """
            select object_key from dataset_files
            where dataset_id = (select id from datasets where name = %s)
              and verification_status = 'verified'
            order by object_key
            """,
            (dataset,),
        ).fetchall()
        return [row[0] for row in rows]

    def read_dataframe(self, key: str) -> pd.DataFrame:
        try:
            response = self.client.get_object(Bucket=self.settings.bucket, Key=key)
        except Exception as exc:
            if str(getattr(exc, "response", {}).get("Error", {}).get("Code", "")) in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                return pd.DataFrame()
            raise
        return pd.read_parquet(io.BytesIO(response["Body"].read()))

    @staticmethod
    def _bounds(frame: pd.DataFrame) -> tuple[str | None, str | None]:
        column = "ts_iso" if "ts_iso" in frame else "ts" if "ts" in frame else None
        if not column or frame.empty:
            return None, None
        values = frame[column].dropna().astype(str)
        if values.empty:
            return None, None
        return values.min(), values.max()

    def write_dataframe(
        self,
        *,
        key: str,
        frame: pd.DataFrame,
        dataset: str,
        source_path: str,
        quality: str = "clean",
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> ManifestEntry:
        """Write a complete immutable-version replacement and atomically catalog it."""
        buffer = io.BytesIO()
        frame.to_parquet(buffer, index=False, compression="snappy")
        payload = buffer.getvalue()
        checksum = hashlib.sha256(payload).hexdigest()
        start, end = self._bounds(frame)
        entry = ManifestEntry(
            dataset=dataset,
            source_path=source_path,
            object_key=key,
            quality=quality,
            symbol=symbol,
            timeframe=timeframe.lower() if timeframe else None,
            range_start=start,
            range_end=end,
            rows=len(frame),
            byte_size=len(payload),
            sha256=checksum,
            compression="SNAPPY",
        )
        previous_entry = None
        try:
            previous_head = self.client.head_object(Bucket=self.settings.bucket, Key=key)
            previous_sha = previous_head.get("Metadata", {}).get("sha256")
        except Exception as exc:
            code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
            if code not in {"404", "NoSuchKey", "NotFound"}:
                raise
            previous_head = None
            previous_sha = None

        if previous_head and previous_sha == checksum:
            self.catalog.record_files([entry], self.settings.bucket)
            return entry
        if previous_head:
            # R2 has no bucket-versioning guarantee. Archive the prior complete
            # version before replacing the current pointer/object.
            previous_frame = self.read_dataframe(key)
            previous_start, previous_end = self._bounds(previous_frame)
            relative_key = key.removeprefix(f"{self.settings.prefix}/")
            archive_key = f"{self.settings.prefix}/versions/{relative_key}/{previous_sha}.parquet"
            self.client.copy_object(
                Bucket=self.settings.bucket,
                Key=archive_key,
                CopySource={"Bucket": self.settings.bucket, "Key": key},
                MetadataDirective="COPY",
            )
            archive_head = self.client.head_object(Bucket=self.settings.bucket, Key=archive_key)
            if archive_head.get("Metadata", {}).get("sha256") != previous_sha:
                raise RuntimeError(f"remote prior-version archive failed: {archive_key}")
            previous_entry = ManifestEntry(
                dataset=f"{dataset}_versions",
                source_path=f"{source_path}#sha256={previous_sha}",
                object_key=archive_key,
                quality=quality,
                symbol=symbol,
                timeframe=timeframe.lower() if timeframe else None,
                range_start=previous_start,
                range_end=previous_end,
                rows=len(previous_frame),
                byte_size=previous_head["ContentLength"],
                sha256=previous_sha,
                compression="SNAPPY",
            )

        self.client.put_object(
            Bucket=self.settings.bucket,
            Key=key,
            Body=payload,
            ContentType="application/vnd.apache.parquet",
            Metadata={"sha256": checksum, "source_path": source_path},
        )
        head = self.client.head_object(Bucket=self.settings.bucket, Key=key)
        if (
            head.get("ContentLength") != len(payload)
            or head.get("Metadata", {}).get("sha256") != checksum
        ):
            raise RuntimeError(f"remote runtime write verification failed: {key}")
        self.catalog.record_files(
            [item for item in (previous_entry, entry) if item is not None],
            self.settings.bucket,
        )
        return entry

    def append_candle(self, symbol: str, timeframe: str, frame: pd.DataFrame) -> ManifestEntry:
        if len(frame) != 1:
            raise ValueError("append_candle expects exactly one normalized candle")
        row = frame.iloc[0]
        day = pd.to_datetime(int(row["ts"]), unit="ms", utc=True).strftime("%Y-%m-%d")
        tf = timeframe.lower()
        key = (
            f"{self.settings.prefix}/market/symbol={symbol.upper()}/timeframe={tf}/"
            f"year={day[:4]}/month={day[5:7]}/{day}.parquet"
        )
        current = self.read_dataframe(key)
        combined = pd.concat([current, frame], ignore_index=True, sort=False)
        combined = (
            combined.drop_duplicates(subset=["symbol", "timeframe", "ts"], keep="last")
            .sort_values("ts")
            .reset_index(drop=True)
        )
        if tf == "15m":
            start = 0
            if "global_x" in current and current["global_x"].notna().any():
                start = int(current["global_x"].min())
            else:
                prefix = f"s3://{self.settings.bucket}/"
                previous = [
                    url[len(prefix):]
                    for url in self.list_candle_urls(tf, symbol)
                    if url[len(prefix):] < key
                ]
                if previous:
                    prior = self.read_dataframe(previous[-1])
                    if "global_x" in prior and prior["global_x"].notna().any():
                        start = int(prior["global_x"].max()) + 1
            # Reindex the complete sorted day so prepends/duplicates cannot create
            # gaps or out-of-order chart indices.
            combined["global_x"] = range(start, start + len(combined))
        return self.write_dataframe(
            key=key,
            frame=combined,
            dataset="market",
            source_path=f"storage/data/{tf}/{day}.parquet",
            symbol=symbol.upper(),
            timeframe=tf,
        )

    def current_objects_key(self) -> str:
        return f"{self.settings.prefix}/objects/current/snapshot.parquet"

    def timeline_key(self, day: str) -> str:
        return f"{self.settings.prefix}/objects/timeline/year={day[:4]}/month={day[5:7]}/{day}.parquet"


@lru_cache(maxsize=1)
def get_remote_store() -> RemoteStore:
    load_runtime_environment()
    return RemoteStore()


def clear_remote_store_cache() -> None:
    """Testing/lifecycle hook; do not leave stale clients across backend switches."""
    get_remote_store.cache_clear()
    load_runtime_environment.cache_clear()
