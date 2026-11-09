"""Move durable engine configuration and JSON state into Postgres.

Revision ID: 0003_runtime_state
Revises: 0002_trade_events
"""

from alembic import op

revision = "0003_runtime_state"
down_revision = "0002_trade_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table runtime_config (
            key text primary key,
            payload jsonb not null,
            updated_at timestamptz not null default now()
        );
        create table runtime_state (
            key text primary key,
            payload jsonb not null,
            updated_at timestamptz not null default now()
        );
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists runtime_state; drop table if exists runtime_config")
