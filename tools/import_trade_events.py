"""Idempotently import the legacy JSONL execution ledger into Postgres."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from paths import OPTIONS_TRADE_LEDGER_PATH
from storage.remote import get_remote_store
from storage.trade_events import insert_trade_payloads


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=OPTIONS_TRADE_LEDGER_PATH)
    args = parser.parse_args()
    payloads = []
    rejected = 0
    with args.path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payloads.append(json.loads(line))
            except json.JSONDecodeError:
                rejected += 1
    inserted = insert_trade_payloads(payloads, source_path=args.path)
    connection = get_remote_store().catalog.connection
    remote_count = connection.execute("select count(*) from trade_events").fetchone()[0]
    print(
        f"[TRADE EVENTS] source_rows={len(payloads)} rejected_json={rejected} "
        f"processed={inserted} remote_rows={remote_count}"
    )
    if rejected:
        raise SystemExit("Invalid JSONL records require review before cutover")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
