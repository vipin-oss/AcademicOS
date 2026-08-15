"""document_revisions — immutable upload revisions (V3 M11)

Revision ID: 0019_document_revisions
Revises: 0018_durable_jobs
Create Date: 2026-08-15

V3 Milestone M11 (ADR-058): one immutable row per upload revision. A new
upload of a document mints a new revision (never overwrites history) — the
explicit-revisions upgrade of the M5 ``source_version`` binding (blueprint
A9). Additive only.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0019_document_revisions"
down_revision = "0018_durable_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_revisions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("revision_version", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("quarantined", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quarantine_reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False, server_default="default"),
        sa.Column("owner_user_id", sa.String(), nullable=False, server_default="default"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_revisions_document", "document_revisions", ["document_id"])
    op.create_index("ix_document_revisions_tenant", "document_revisions", ["tenant_id"])
    op.create_index("ix_document_revisions_owner", "document_revisions", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_document_revisions_owner", table_name="document_revisions")
    op.drop_index("ix_document_revisions_tenant", table_name="document_revisions")
    op.drop_index("ix_document_revisions_document", table_name="document_revisions")
    op.drop_table("document_revisions")
