"""search_documents projection table

Revision ID: 0005_search_documents
Revises: 0004_object_versions
Create Date: 2026-08-06

Sprint-5 Milestone 1 — Global Search Foundation. The persistent, derived
search projection: one row per object's current searchable state, written
ONLY by the outbox consumer (never by the object write path), with the
``version`` guard making index writes version-aware.

Design notes:

- No FK to ``objects``: the projection is eventually consistent and derived
  — the relay removes rows for deleted objects; a FK cascade would couple
  the index to the authoritative store's lifecycle and diverge between
  engines. The index is never the source of truth.
- ``UNIQUE`` on ``object_id`` (the primary key): one projection per object,
  so replaying the outbox can never duplicate index rows.
- Plain btree indexes for the exact-match surface (``object_type``);
  full-text matching uses literal-substring LIKE over ``title`` /
  ``metadata_text`` — the simple full-text matching supported by the
  existing persistence layer, no dedicated engine.
- No backfill: rows exist for events drained after this migration (the
  relay is the only writer; backfilling would violate the roadmap invariant
  that index consumers ride the relay, never backfill).

Downgrade drops the table (a derived projection — the objects themselves
are untouched).
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_search_documents"
down_revision = "0004_object_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_documents",
        sa.Column("object_id", sa.String(), primary_key=True),
        sa.Column("object_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("metadata_text", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_search_documents_object_type", "search_documents", ["object_type"]
    )


def downgrade() -> None:
    op.drop_index("ix_search_documents_object_type", table_name="search_documents")
    op.drop_table("search_documents")
