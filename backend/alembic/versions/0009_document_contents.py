"""document_contents — document-content search projection

Revision ID: 0009_document_contents
Revises: 0008_document_annotations
Create Date: 2026-08-10

The document-content search projection (M27). Derived data only — never
authoritative domain state. Populated at intake-commit time from the
extracted-text blob (the blob remains the source of truth), rebuildable
from storage, and removed when the owning DOCUMENT object is deleted.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0009_document_contents"
down_revision = "0008_document_annotations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_contents",
        sa.Column("object_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("source_item_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["object_id"], ["objects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("object_id"),
    )


def downgrade() -> None:
    op.drop_table("document_contents")
