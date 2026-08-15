"""saved_views — ad-hoc query/export definitions (V3 M13)

Revision ID: 0021_saved_views
Revises: 0020_spend_ledger
Create Date: 2026-08-15

V3 Milestone M13 (ADR-060): store saved ad-hoc query/export definitions as
JSON (compiled to parameterized SQL at run time, never executed verbatim).
Additive only.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0021_saved_views"
down_revision = "0020_spend_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_views",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False, server_default="default"),
        sa.Column("owner_user_id", sa.String(), nullable=False, server_default="default"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_views_tenant", "saved_views", ["tenant_id"])
    op.create_index("ix_saved_views_owner", "saved_views", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_saved_views_owner", table_name="saved_views")
    op.drop_index("ix_saved_views_tenant", table_name="saved_views")
    op.drop_table("saved_views")
