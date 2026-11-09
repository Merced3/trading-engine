"""Postgres catalog writes for verified R2 objects."""

from __future__ import annotations

import os
from typing import Any

import psycopg

from storage.lake_migration import ManifestEntry, RejectedFile


class PostgresCatalog:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    @classmethod
    def from_env(cls) -> "PostgresCatalog":
        url = os.getenv("TRADING_DATABASE_URL")
        if not url:
            raise RuntimeError("Missing Postgres setting: TRADING_DATABASE_URL")
        return cls(psycopg.connect(url))

    def close(self) -> None:
        self.connection.close()

    def record_file(self, entry: ManifestEntry, bucket: str) -> None:
        self.record_files([entry], bucket)

    def record_files(self, entries: list[ManifestEntry], bucket: str) -> None:
        """Catalog a verified batch in one transaction, not one transaction/file."""
        if not entries:
            return
        with self.connection.transaction():
            dataset_ids: dict[tuple[str, str], int] = {}
            for dataset, prefix in sorted(
                {(entry.dataset, entry.object_key.split("/", 1)[0]) for entry in entries}
            ):
                dataset_ids[(dataset, prefix)] = self.connection.execute(
                    """
                    insert into datasets (name, r2_prefix)
                    values (%s, %s)
                    on conflict (name) do update set r2_prefix = excluded.r2_prefix
                    returning id
                    """,
                    (dataset, prefix),
                ).fetchone()[0]
            rows = [
                (
                    dataset_ids[(entry.dataset, entry.object_key.split("/", 1)[0])],
                    bucket,
                    entry.object_key,
                    entry.source_path,
                    entry.quality,
                    entry.symbol,
                    entry.timeframe,
                    entry.range_start,
                    entry.range_end,
                    entry.rows,
                    entry.byte_size,
                    entry.sha256,
                    entry.compression,
                )
                for entry in entries
            ]
            with self.connection.cursor() as cursor:
                cursor.executemany(
                    """
                insert into dataset_files (
                    dataset_id, bucket, object_key, source_path, quality, symbol,
                    timeframe, range_start, range_end, row_count, byte_size, sha256,
                    compression, verification_status, verified_at
                ) values (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    'verified', now()
                )
                on conflict (bucket, object_key) do update set
                    dataset_id = excluded.dataset_id,
                    source_path = excluded.source_path,
                    quality = excluded.quality,
                    symbol = excluded.symbol,
                    timeframe = excluded.timeframe,
                    range_start = excluded.range_start,
                    range_end = excluded.range_end,
                    row_count = excluded.row_count,
                    byte_size = excluded.byte_size,
                    sha256 = excluded.sha256,
                    compression = excluded.compression,
                    verification_status = 'verified',
                    verified_at = now()
                """,
                rows,
            )

    def record_rejection(self, rejection: RejectedFile) -> None:
        self.connection.execute(
            """
            insert into migration_rejections (source_path, byte_size, reason)
            values (%s, %s, %s)
            on conflict (source_path) do update set
                byte_size = excluded.byte_size,
                reason = excluded.reason,
                discovered_at = now()
            """,
            (rejection.source_path, rejection.byte_size, rejection.reason),
        )
        self.connection.commit()
