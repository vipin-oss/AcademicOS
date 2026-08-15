"""document_search_fts + document_registry — scale & identity projections (P1)

Revision ID: 0011_search_fts_identity
Revises: 0010_document_chunks
Create Date: 2026-08-12

Adds two DERIVED projections (never a source of truth):

- ``document_search_fts`` — PostgreSQL tsvector (``simple`` config,
  deterministic) GENERATED column + GIN index over title/metadata/content/
  chunks text. (SQLite gets the FTS5 virtual table via ``ensure_fts_schema``
  in ``init_db.py`` — alembic does not manage virtual tables.)
- ``document_registry`` — the content-identity registry keyed by
  ``content_hash`` (sha256 of NORMALIZED extracted text): canonical
  document id (smallest object_id — deterministic) + document count for
  duplicate detection.
- an index on ``document_contents.content_hash`` (the identity signal).

Both are maintained by the SAME single index consumer (SearchIndexApplier)
and the rebuild path. Rollback drops both tables and the index — pure
additive derived data.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0011_search_fts_identity"
down_revision = "0010_document_chunks"
branch_labels = None
depends_on = None

_PG_FTS_DDL = """
CREATE TABLE IF NOT EXISTS document_search_fts (
    object_id VARCHAR PRIMARY KEY,
    object_type VARCHAR NOT NULL,
    version INTEGER NOT NULL,
    title TEXT NOT NULL,
    metadata_text TEXT NOT NULL DEFAULT '',
    content_text TEXT NOT NULL DEFAULT '',
    chunks_text TEXT NOT NULL DEFAULT '',
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector(
            'simple',
            coalesce(title, '') || ' ' || coalesce(metadata_text, '') || ' ' ||
            coalesce(content_text, '') || ' ' || coalesce(chunks_text, '')
        )
    ) STORED
);
CREATE INDEX IF NOT EXISTS ix_document_search_fts_vec
    ON document_search_fts USING GIN (search_vector);
"""


def upgrade() -> None:
    bind = op.get_bind()
    op.create_index(
        "ix_document_contents_content_hash",
        "document_contents",
        ["content_hash"],
    )
    op.create_table(
        "document_registry",
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("canonical_document_id", sa.String(), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("content_hash"),
    )
    if bind.dialect.name == "postgresql":
        op.execute(_PG_FTS_DDL)
    # SQLite: FTS5 virtual table created by ensure_fts_schema (init_db.py).


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TABLE IF EXISTS document_search_fts")
    op.drop_table("document_registry")
    op.drop_index("ix_document_contents_content_hash", table_name="document_contents")
