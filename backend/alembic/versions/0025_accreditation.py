"""accreditation_submissions — accreditation workflow (V3 M18)

Revision ID: 0025_accreditation
Revises: 0024_temporal_graph_identity
Create Date: 2026-08-15

V3 Milestone M18 (ADR-065): the accreditation workflow kernel. One row per
criterion/indicator submission; lifecycle draft -> submitted -> approved/
rejected, then period LOCK (irreversible attestation). Additive only.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0025_accreditation"
down_revision = "0024_temporal_graph_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accreditation_submissions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("framework_id", sa.String(), nullable=False),
        sa.Column("criterion_id", sa.String(), nullable=False),
        sa.Column("indicator_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("evidence", sa.String(), nullable=False, server_default="[]"),
        sa.Column("narrative", sa.String(), nullable=False, server_default=""),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.Column("period", sa.String(), nullable=False, server_default=""),
        sa.Column("period_locked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False, server_default="default"),
        sa.Column("owner_user_id", sa.String(), nullable=False, server_default="default"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_accreditation_framework", "accreditation_submissions", ["framework_id"])


def downgrade() -> None:
    op.drop_index("ix_accreditation_framework", table_name="accreditation_submissions")
    op.drop_table("accreditation_submissions")
