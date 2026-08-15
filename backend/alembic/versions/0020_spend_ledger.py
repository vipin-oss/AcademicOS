"""spend_ledger — append-only AI spend audit (V3 M12)

Revision ID: 0020_spend_ledger
Revises: 0019_document_revisions
Create Date: 2026-08-15

V3 Milestone M12 (ADR-059): append-only spend audit for AI generations, keyed
by tenant/user/provider/model with token counts + estimated cost. The budget
policy aggregates this ledger; it is never updated/deleted (immutable audit).
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0020_spend_ledger"
down_revision = "0019_document_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spend_ledger",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider_id", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False, server_default="default"),
        sa.Column("owner_user_id", sa.String(), nullable=False, server_default="default"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_spend_ledger_user", "spend_ledger", ["user_id"])
    op.create_index("ix_spend_ledger_tenant", "spend_ledger", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_spend_ledger_tenant", table_name="spend_ledger")
    op.drop_index("ix_spend_ledger_user", table_name="spend_ledger")
    op.drop_table("spend_ledger")
