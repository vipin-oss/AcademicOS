"""document_chunks — deterministic chunk projection + content_hash (P0)

Revision ID: 0010_document_chunks
Revises: 0009_document_contents
Create Date: 2026-08-12

Adds the derived, rebuildable chunk projection of the knowledge layer:

- ``document_contents.content_hash`` — sha256 of the normalized extracted
  text; NULL until backfilled by the rebuild (change-detection authority,
  NOT a new source of truth);
- ``document_chunks`` — deterministic segmentation of the normalized
  content: PK (document_id, chunk_index), FK to objects ON DELETE CASCADE,
  CHECK char_end > char_start, index on content_hash.

Pure additive derived data: rollback drops the table and the column.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_document_chunks"
down_revision = "0009_document_contents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_contents",
        sa.Column("content_hash", sa.String(), nullable=True),
    )
    op.create_table(
        "document_chunks",
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_item_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.CheckConstraint("char_end > char_start", name="ck_document_chunks_span"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["objects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("document_id", "chunk_index"),
    )
    op.create_index(
        "ix_document_chunks_content_hash", "document_chunks", ["content_hash"]
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_content_hash", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_column("document_contents", "content_hash")
