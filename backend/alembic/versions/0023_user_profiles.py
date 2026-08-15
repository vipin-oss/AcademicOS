"""user_profiles — normalization wave 1: user_state (V3 M16)

Revision ID: 0023_user_profiles
Revises: 0022_organizations_memberships
Create Date: 2026-08-15

V3 Milestone M16 (ADR-063): typed projection of the user object's hot fields.
Derived, rebuildable data — the USER object stays the source of truth.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0023_user_profiles"
down_revision = "0022_organizations_memberships"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("roles", sa.String(), nullable=False, server_default="[]"),
        sa.Column("institution", sa.String(), nullable=True),
        sa.Column("tenant_id", sa.String(), nullable=False, server_default="default"),
        sa.Column("owner_user_id", sa.String(), nullable=False, server_default="default"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("ix_user_profiles_username", "user_profiles", ["username"])


def downgrade() -> None:
    op.drop_index("ix_user_profiles_username", table_name="user_profiles")
    op.drop_table("user_profiles")
