"""Postgres-backed execution ledger used when remote storage is enabled."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from psycopg.types.json import Jsonb

from options.trade_ledger import TradeEvent
from storage.remote import get_remote_store

_COLUMNS = (
    "occurred_at",
    "event_type",
    "position_id",
    "order_id",
    "strategy_tag",
    "symbol",
    "timeframe",
    "option_type",
    "strike",
    "expiration",
    "contract_key",
    "quantity",
    "fill_price",
    "total_value",
    "avg_entry",
    "quantity_open",
    "position_status",
    "realized_pnl",
    "reason",
)


def _values(payload: dict) -> list:
    tag = payload.get("strategy_tag")
    timeframe = tag.rsplit("-", 1)[-1].lower() if tag and "-" in tag else None
    return [
        payload.get("ts"),
        payload.get("event"),
        payload.get("position_id"),
        payload.get("order_id"),
        tag,
        payload.get("symbol"),
        timeframe,
        payload.get("option_type"),
        payload.get("strike"),
        payload.get("expiration"),
        payload.get("contract_key"),
        payload.get("quantity"),
        payload.get("fill_price"),
        payload.get("total_value"),
        payload.get("avg_entry"),
        payload.get("quantity_open"),
        payload.get("position_status"),
        payload.get("realized_pnl"),
        payload.get("reason"),
    ]


def insert_trade_payloads(
    payloads: Iterable[dict],
    *,
    source_path: Path | None = None,
) -> int:
    rows = []
    for line, payload in enumerate(payloads, start=1):
        if not payload.get("position_id") or not payload.get("ts"):
            continue
        rows.append(
            (
                *_values(payload),
                Jsonb(payload),
                str(source_path) if source_path else None,
                line if source_path else None,
            )
        )
    if not rows:
        return 0
    connection = get_remote_store().catalog.connection
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.executemany(
                f"""
                insert into trade_events (
                    {', '.join(_COLUMNS)}, payload, source_path, source_line
                ) values ({', '.join(['%s'] * (len(_COLUMNS) + 3))})
                on conflict (source_path, source_line) do nothing
                """,
                rows,
            )
    return len(rows)


def record_trade_event(event: TradeEvent) -> None:
    insert_trade_payloads([asdict(event)])


def load_trade_payloads() -> list[dict]:
    connection = get_remote_store().catalog.connection
    rows = connection.execute(
        "select payload from trade_events order by occurred_at, id"
    ).fetchall()
    return [row[0] for row in rows]


def sum_realized_pnl_for_day(trading_day: str) -> float:
    connection = get_remote_store().catalog.connection
    value = connection.execute(
        """
        select coalesce(sum(realized_pnl), 0)
        from trade_events
        where event_type = 'close'
          and (occurred_at at time zone 'America/New_York')::date = %s::date
        """,
        (trading_day,),
    ).fetchone()[0]
    return float(value)
