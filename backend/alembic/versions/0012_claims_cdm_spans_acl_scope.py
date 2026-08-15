"""L1 knowledge-plane contracts: claims, CDM blocks, polymorphic spans, acl_scope.

Revision ID: 0012_claims_cdm_spans_acl_scope
Revises: 0011_search_fts_identity
Create Date: 2026-08-13

Adds the L1 knowledge-plane schema (all ADR-gated, format-agnostic):

- ``claims``        — the single AI-visible fact source (ADR-002, ADR-019).
  Bound to the registry-driven predicate catalogue; ``claim_id`` is the
  idempotency key; status PROPOSED/CONFIRMED/REJECTED/SUPERSEDED (ADR-006/021).
- ``claim_spans``   — polymorphic span provenance (ADR-003): page/block/char/
  bbox/cell/slide/equation region; never page-only.
- ``cdm_blocks``    — structured-document block store (Blueprint §11),
  format-agnostic (heading/table/figure/caption/footnote/equation/...).
- ``acl_scope`` on existing derived projections (ADR-009): search_documents,
  document_contents, document_chunks (and document_search_fts on PostgreSQL),
  so retrieval/evidence can pre-filter without a second object lookup.
- ``document_chunks.page`` + ``region_json`` polymorphic span anchors (ADR-003).

Pure additive. Rollback drops the new tables and additive columns only.
SQLite FTS acl_scope is handled by ``ensure_fts_schema`` (init_db.py), not by
alembic (FTS5 virtual tables are not alembic-managed).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0012_claims_cdm_spans_acl_scope"
down_revision = "0011_search_fts_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # --- derived projections: acl_scope (ADR-009) ---------------------------
    op.add_column("search_documents", sa.Column("acl_scope", sa.String(), nullable=True))
    op.add_column("document_contents", sa.Column("acl_scope", sa.String(), nullable=True))
    op.add_column("document_chunks", sa.Column("acl_scope", sa.String(), nullable=True))
    # polymorphic span anchors on chunks (ADR-003)
    op.add_column("document_chunks", sa.Column("page", sa.Integer(), nullable=True))
    op.add_column(
        "document_chunks", sa.Column("region_json", sa.JSON(), nullable=True)
    )

    if dialect == "postgresql":
        op.execute(
            "ALTER TABLE document_search_fts ADD COLUMN acl_scope VARCHAR"
        )
        op.create_index(
            "ix_search_documents_acl_scope", "search_documents", ["acl_scope"]
        )
        op.create_index(
            "ix_document_chunks_acl_scope", "document_chunks", ["acl_scope"]
        )
        op.create_index(
            "ix_document_contents_acl_scope", "document_contents", ["acl_scope"]
        )

    # --- claims -------------------------------------------------------------
    op.create_table(
        "claims",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("claim_id", sa.String(), nullable=False, unique=True),
        sa.Column("predicate_id", sa.String(), nullable=False),
        sa.Column("predicate_version", sa.Integer(), nullable=False),
        sa.Column("value_schema", sa.String(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("source_document_id", sa.String(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("provenance", sa.String(), nullable=False),
        sa.Column("fact_confidence", sa.Float(), nullable=True),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("acl_scope", sa.String(), nullable=True),
        sa.Column("supersedes_claim_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=True),
    )
    op.create_index("ix_claims_source_document", "claims", ["source_document_id"])
    op.create_index("ix_claims_predicate", "claims", ["predicate_id", "status"])
    op.create_index("ix_claims_status", "claims", ["status"])
    op.create_index("ix_claims_acl_scope", "claims", ["acl_scope"])

    # --- polymorphic claim spans (ADR-003) ----------------------------------
    op.create_table(
        "claim_spans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("span_id", sa.String(), nullable=False, unique=True),
        sa.Column("claim_id", sa.String(), nullable=False),
        sa.Column("span_kind", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("block_id", sa.String(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("row_idx", sa.Integer(), nullable=True),
        sa.Column("col_idx", sa.Integer(), nullable=True),
        sa.Column("table_id", sa.String(), nullable=True),
        sa.Column("slide", sa.Integer(), nullable=True),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("region", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("ix_claim_spans_claim_id", "claim_spans", ["claim_id"])
    op.create_index("ix_claim_spans_source", "claim_spans", ["source_id", "span_kind"])

    # --- CDM blocks (Blueprint §11) -----------------------------------------
    op.create_table(
        "cdm_blocks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("block_id", sa.String(), nullable=False, unique=True),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("block_type", sa.String(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("parent_block_id", sa.String(), nullable=True),
        sa.Column("acl_scope", sa.String(), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("ix_cdm_blocks_document", "cdm_blocks", ["document_id", "version"])
    op.create_index("ix_cdm_blocks_parent", "cdm_blocks", ["parent_block_id"])
    op.create_index("ix_cdm_blocks_type", "cdm_blocks", ["block_type"])
    op.create_index("ix_cdm_blocks_acl_scope", "cdm_blocks", ["acl_scope"])


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.drop_table("cdm_blocks")
    op.drop_table("claim_spans")
    op.drop_table("claims")

    op.drop_column("document_chunks", "region_json")
    op.drop_column("document_chunks", "page")
    op.drop_column("document_chunks", "acl_scope")
    op.drop_column("document_contents", "acl_scope")
    op.drop_column("search_documents", "acl_scope")

    if dialect == "postgresql":
        op.execute("ALTER TABLE document_search_fts DROP COLUMN IF EXISTS acl_scope")
        op.drop_index("ix_search_documents_acl_scope", table_name="search_documents")
        op.drop_index("ix_document_chunks_acl_scope", table_name="document_chunks")
        op.drop_index("ix_document_contents_acl_scope", table_name="document_contents")
