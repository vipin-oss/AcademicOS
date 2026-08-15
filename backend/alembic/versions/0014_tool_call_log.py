"""L5 tool-call audit log table (ADR-037, Freeze Contract §13.5.6).

Revision ID: 0014_tool_call_log
Revises: 0013_claim_cdm_decisions
Create Date: 2026-08-13

Adds ``tool_call_log`` — append-only, idempotent-by-``call_id`` audit of every
L5 tool call (tool identity, principal, acl_scope, ok, cost_class). Does not
store sensitive payloads. Pure additive; rollback drops the table.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0014_tool_call_log"
down_revision = "0013_claim_cdm_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_call_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("call_id", sa.String(), nullable=False, unique=True),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("principal", sa.String(), nullable=False),
        sa.Column("acl_scope", sa.String(), nullable=True),
        sa.Column("ok", sa.Integer(), nullable=False),
        sa.Column("cost_class", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index(
        "ix_tool_call_log_tool_principal", "tool_call_log", ["tool_name", "principal"]
    )


def downgrade() -> None:
    op.drop_table("tool_call_log")
