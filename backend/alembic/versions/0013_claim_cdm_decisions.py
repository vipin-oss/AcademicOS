"""L3 confirmation audit: claim_decisions + cdm_decisions tables.

Revision ID: 0013_claim_cdm_decisions
Revises: 0012_claims_cdm_spans_acl_scope
Create Date: 2026-08-13

Adds the L3 Human-in-the-Loop decision audit tables (ADR-032):

- ``claim_decisions`` — append-only, idempotent-by-``decision_id`` audit of
  every approve/reject/correct on a claim (reviewer, previous/resulting status,
  notes, acl_scope, eval_run_id, created_at).
- ``cdm_decisions`` — same for CDM-block approve/reject.

These are CLAIM/CDM-scoped decision logs, deliberately NOT the
conversation-scoped ``review_decisions`` table (no coupling to assistant
reviews). L1 claim/cdm tables are NOT modified.

Pure additive; rollback drops the two tables.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0013_claim_cdm_decisions"
down_revision = "0012_claims_cdm_spans_acl_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "claim_decisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("decision_id", sa.String(), nullable=False, unique=True),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("reviewer", sa.String(), nullable=False),
        sa.Column("previous_status", sa.String(), nullable=False),
        sa.Column("resulting_status", sa.String(), nullable=False),
        sa.Column("notes", sa.String(), nullable=False),
        sa.Column("acl_scope", sa.String(), nullable=True),
        sa.Column("eval_run_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("ix_claim_decisions_claim_id", "claim_decisions", ["subject_id"])
    op.create_index(
        "ix_claim_decisions_reviewer", "claim_decisions", ["reviewer", "created_at"]
    )

    op.create_table(
        "cdm_decisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("decision_id", sa.String(), nullable=False, unique=True),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("reviewer", sa.String(), nullable=False),
        sa.Column("previous_status", sa.String(), nullable=False),
        sa.Column("resulting_status", sa.String(), nullable=False),
        sa.Column("notes", sa.String(), nullable=False),
        sa.Column("acl_scope", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("ix_cdm_decisions_block_id", "cdm_decisions", ["subject_id"])


def downgrade() -> None:
    op.drop_table("cdm_decisions")
    op.drop_table("claim_decisions")
