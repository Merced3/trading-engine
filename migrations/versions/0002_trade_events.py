"""Store execution/trade analytics events in Postgres.

Revision ID: 0002_trade_events
Revises: 0001_data_lake_catalog
"""

from alembic import op

revision = "0002_trade_events"
down_revision = "0001_data_lake_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table trade_events (
            id bigint generated always as identity primary key,
            occurred_at timestamptz not null,
            event_type text not null,
            position_id text not null,
            order_id text,
            strategy_tag text,
            symbol text not null,
            timeframe text,
            option_type text,
            strike double precision,
            expiration text,
            contract_key text,
            quantity integer,
            fill_price double precision,
            total_value double precision,
            avg_entry double precision,
            quantity_open integer,
            position_status text,
            realized_pnl double precision,
            reason text,
            payload jsonb not null,
            source_path text,
            source_line integer,
            created_at timestamptz not null default now(),
            unique (source_path, source_line)
        );
        create index trade_events_position on trade_events (position_id, occurred_at);
        create index trade_events_strategy on trade_events (strategy_tag, occurred_at);
        create index trade_events_day on trade_events (occurred_at, event_type);
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists trade_events")
