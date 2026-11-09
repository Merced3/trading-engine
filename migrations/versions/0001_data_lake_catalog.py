"""Create the Parquet/R2 catalog.

Revision ID: 0001_data_lake_catalog
Revises:
"""

from alembic import op

revision = "0001_data_lake_catalog"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table datasets (
            id bigint generated always as identity primary key,
            name text not null unique,
            schema_version integer not null default 1,
            r2_prefix text not null,
            status text not null default 'active' check (status in ('active', 'archived')),
            created_at timestamptz not null default now()
        );

        create table dataset_files (
            id bigint generated always as identity primary key,
            dataset_id bigint not null references datasets(id) on delete restrict,
            bucket text not null,
            object_key text not null,
            source_path text not null,
            quality text not null check (quality in ('clean', 'faulty', 'snapshot')),
            symbol text,
            timeframe text,
            range_start text,
            range_end text,
            row_count bigint not null check (row_count >= 0),
            byte_size bigint not null check (byte_size > 0),
            sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
            compression text not null,
            verification_status text not null
                check (verification_status in ('pending', 'verified', 'failed')),
            uploaded_at timestamptz not null default now(),
            verified_at timestamptz,
            unique (bucket, object_key),
            unique (dataset_id, source_path)
        );
        create index dataset_files_lookup
            on dataset_files (dataset_id, symbol, timeframe, range_start);
        create index dataset_files_checksum on dataset_files (sha256);

        create table migration_rejections (
            id bigint generated always as identity primary key,
            source_path text not null unique,
            byte_size bigint not null check (byte_size >= 0),
            reason text not null,
            discovered_at timestamptz not null default now()
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        drop table if exists migration_rejections;
        drop table if exists dataset_files;
        drop table if exists datasets;
        """
    )
