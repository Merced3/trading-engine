"""Durable JSON configuration/state stored in Postgres in remote mode."""

from __future__ import annotations

from pathlib import Path

from psycopg.types.json import Jsonb

from paths import BASE
from storage.remote import get_remote_store

_MISSING = object()


def state_key(path: Path) -> str:
    try:
        return path.resolve().relative_to(BASE.resolve()).as_posix()
    except ValueError:
        return str(path)


def read_state(path: Path, default=None):
    connection = get_remote_store().catalog.connection
    row = connection.execute(
        "select payload from runtime_state where key = %s", (state_key(path),)
    ).fetchone()
    return default if row is None else row[0]


def write_state(path: Path, payload) -> None:
    connection = get_remote_store().catalog.connection
    connection.execute(
        """
        insert into runtime_state (key, payload) values (%s, %s)
        on conflict (key) do update set payload = excluded.payload, updated_at = now()
        """,
        (state_key(path), Jsonb(payload)),
    )
    connection.commit()


def read_config() -> dict:
    connection = get_remote_store().catalog.connection
    row = connection.execute(
        "select payload from runtime_config where key = 'engine'"
    ).fetchone()
    if row is None:
        raise RuntimeError("Remote engine config is missing; run tools/import_runtime_state.py")
    return row[0]


def update_config_value(key: str, value) -> None:
    connection = get_remote_store().catalog.connection
    with connection.transaction():
        row = connection.execute(
            "select payload from runtime_config where key = 'engine' for update"
        ).fetchone()
        if row is None:
            raise RuntimeError("Remote engine config is missing; run tools/import_runtime_state.py")
        payload = dict(row[0])
        payload[key] = value
        connection.execute(
            "update runtime_config set payload = %s, updated_at = now() where key = 'engine'",
            (Jsonb(payload),),
        )
