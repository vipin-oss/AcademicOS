"""typed claim columns — the rung-0 fast path (V3 M5)

Revision ID: 0016_typed_claims
Revises: 0015_tenancy_stamping
Create Date: 2026-08-14

V3 Milestone M5 (blueprint §M5, audit A1): add writer-populated typed
projections of ``claims.value`` so rung-0 fact lookups are an indexed scan
instead of a JSONB scan (ORDER BY / BETWEEN / SUM over ``value`` cannot use an
index). Additive only — ``value`` stays the authoritative source.

- ``value_number`` (NUMERIC) — the ``amount`` of a money value.
- ``value_date`` / ``value_text`` (TEXT) — the ``value`` of date/text values.

Writer-populated, not ``GENERATED``: the JSON extraction expression is
dialect-specific (Postgres JSONB ``->>`` vs SQLite ``json_extract``) and not
IMMUTABLE-portable, so the claim writer populates them (blueprint A1 fallback).

Rollback: drop the columns and indexes — pure additive derived data.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0016_typed_claims"
down_revision = "0015_tenancy_stamping"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("claims", sa.Column("value_number", sa.Float(), nullable=True))
    op.add_column("claims", sa.Column("value_text", sa.String(), nullable=True))
    op.add_column("claims", sa.Column("value_date", sa.String(), nullable=True))
    op.create_index(
        "ix_claims_predicate_number", "claims", ["predicate_id", "value_number"]
    )
    op.create_index(
        "ix_claims_predicate_date", "claims", ["predicate_id", "value_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_claims_predicate_date", table_name="claims")
    op.drop_index("ix_claims_predicate_number", table_name="claims")
    op.drop_column("claims", "value_date")
    op.drop_column("claims", "value_text")
    op.drop_column("claims", "value_number")
