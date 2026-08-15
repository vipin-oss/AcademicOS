"""organizations + memberships — multi-tenant isolation (V3 M15)

Revision ID: 0022_organizations_memberships
Revises: 0021_saved_views
Create Date: 2026-08-15

V3 Milestone M15 (ADR-062): organizations (tenants) with lifecycle status and
per-tenant storage quota + spend cap, plus memberships binding users to
organizations with a scoped role. Isolation is via the M3 tenant_id stamp,
enforced by the M9 flag + the saved-view/search tenant predicates.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0022_organizations_memberships"
down_revision = "0021_saved_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("storage_quota_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("spend_cap_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False, server_default="default"),
        sa.Column("owner_user_id", sa.String(), nullable=False, server_default="default"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organizations_tenant", "organizations", ["tenant_id"])

    op.create_table(
        "memberships",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False, server_default="default"),
        sa.Column("owner_user_id", sa.String(), nullable=False, server_default="default"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memberships_org", "memberships", ["organization_id"])
    op.create_index("ix_memberships_user", "memberships", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_memberships_user", table_name="memberships")
    op.drop_index("ix_memberships_org", table_name="memberships")
    op.drop_table("memberships")
    op.drop_index("ix_organizations_tenant", table_name="organizations")
    op.drop_table("organizations")
