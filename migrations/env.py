"""Alembic environment; the database URL comes only from the environment."""

import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

project_root = Path(__file__).resolve().parents[1]
load_dotenv(project_root / ".env")
load_dotenv(project_root.parent.parent / "ops" / "env" / "data-platform.env")
config = context.config
url = os.environ.get("TRADING_MIGRATION_DATABASE_URL") or os.environ.get(
    "TRADING_DATABASE_URL"
)
if not url:
    raise RuntimeError("TRADING_DATABASE_URL is required for catalog migrations")
# The platform reserves direct 25060 for migrations; apps use PgBouncer 25061.
parts = urlsplit(url)
if not os.environ.get("TRADING_MIGRATION_DATABASE_URL") and parts.port == 25061:
    url = urlunsplit(parts._replace(netloc=parts.netloc.replace(":25061", ":25060")))
if url.startswith("postgresql://"):
    url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
config.set_main_option("sqlalchemy.url", url)


def run_migrations_offline() -> None:
    context.configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(724918230105)")
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
