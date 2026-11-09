"""Import existing config.json and durable storage JSON state without overwriting remote state."""

from __future__ import annotations

import json

from psycopg.types.json import Jsonb

from paths import BASE, CONFIG_PATH, STORAGE_DIR
from storage.remote import get_remote_store
from storage.runtime_state import state_key


def main() -> int:
    connection = get_remote_store().catalog.connection
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config_result = connection.execute(
        """
        insert into runtime_config (key, payload) values ('engine', %s)
        on conflict (key) do nothing
        """,
        (Jsonb(config),),
    )
    imported = 0
    skipped = 0
    for path in sorted(STORAGE_DIR.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"[STATE] rejected invalid JSON: {path.relative_to(BASE)}")
            continue
        result = connection.execute(
            """
            insert into runtime_state (key, payload) values (%s, %s)
            on conflict (key) do nothing
            """,
            (state_key(path), Jsonb(payload)),
        )
        if result.rowcount:
            imported += 1
        else:
            skipped += 1
    connection.commit()
    config_count = connection.execute("select count(*) from runtime_config").fetchone()[0]
    state_count = connection.execute("select count(*) from runtime_state").fetchone()[0]
    print(
        f"[STATE] config_rows={config_count} imported={imported} existing={skipped} "
        f"remote_state_rows={state_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
