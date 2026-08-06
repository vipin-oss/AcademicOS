"""object_versions snapshot table

Revision ID: 0004_object_versions
Revises: 0003_outbox_events
Create Date: 2026-08-06

Sprint-4 Milestone B — immutable version snapshots. Every version an Object
has ever stored gets one row, written in the SAME transaction as the save
that produced it (the repository appends the row inside its write lambda,
alongside the outbox rows). ``snapshot`` holds the existing
``ObjectSnapshot.to_dict()`` representation — no new serialization format
was invented for versioning.

Design notes:

- ``UNIQUE (object_id, version)`` is the duplicate guard: one immutable row
  per version of an object, enforced by the database.
- ``object_id`` FK -> objects ON DELETE CASCADE (PostgreSQL); the repository
  deletes version rows explicitly so SQLite behaves identically (the same
  doctrine as the edge table).
- No backfill: rows exist for versions saved after this migration. Nothing
  reads the table yet, so pre-migration versions simply have no rows and no
  behavior changes.

Downgrade drops the table (version snapshots are derived records of committed
state — the objects themselves are untouched).
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_object_versions"
down_revision = "0003_outbox_events"
branch_labels = None
depends_on = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    is_pg = _is_postgresql()
    json_type = postgresql.JSONB() if is_pg else sa.JSON()

    op.create_table(
        "object_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "object_id",
            sa.String(),
            sa.ForeignKey("objects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", json_type, nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint(
            "object_id", "version", name="uq_object_versions_object_id_version"
        ),
    )


def downgrade() -> None:
    op.drop_table("object_versions")
