"""tenancy stamping — tenant_id + owner_user_id on every table (V3 M3)

Revision ID: 0015_tenancy_stamping
Revises: 0014_tool_call_log
Create Date: 2026-08-14

V3 Milestone M3 (blueprint §M3, correcting audit A7): add ``tenant_id`` +
``owner_user_id`` to all 18 tables (17 ORM + ``document_search_fts``). Columns
only — **no enforcement**. Reads stay open; ownership/tenant filtering is M9.

- Both columns are ``NOT NULL DEFAULT 'default'`` (single-tenant present), so
  the ALTER backfills every existing row to ``'default'`` in one pass and no
  write path can produce a NULL.
- ``document_chunks`` has a composite PK ``(document_id, chunk_index)``; it is
  deliberately NOT touched — a tenancy partition key does not belong in that
  PK, and enforcement (M9) will scope queries rather than alter the key.
- The ``document_search_fts`` generated tsvector expression is UNCHANGED here:
  tenancy stamping is a plain additive column (no table rewrite). The generated
  column rewrite belongs to M4, where the Hindi tokenizer change forces it —
  exactly one rewrite, not two (blueprint §M4 entry condition).

Rollback: drop the columns and indexes (they are unused by logic).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0015_tenancy_stamping"
down_revision = "0014_tool_call_log"
branch_labels = None
depends_on = None

#: Every ORM table present at 0014 (17), plus the raw-DDL FTS table handled below.
_TABLES = (
    "cdm_blocks",
    "cdm_decisions",
    "claim_decisions",
    "claim_spans",
    "claims",
    "document_annotations",
    "document_chunks",
    "document_contents",
    "document_registry",
    "eval_runs",
    "object_relationships",
    "object_versions",
    "objects",
    "outbox_events",
    "review_decisions",
    "search_documents",
    "tool_call_log",
)


def _index_name(table: str, column: str) -> str:
    return f"ix_{table}_{column}"


def upgrade() -> None:
    bind = op.get_bind()
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "tenant_id", sa.String(), nullable=False, server_default="default"
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "owner_user_id", sa.String(), nullable=False, server_default="default"
            ),
        )
        op.create_index(_index_name(table, "tenant_id"), table, ["tenant_id"])
        op.create_index(_index_name(table, "owner_user_id"), table, ["owner_user_id"])

    # document_search_fts is raw DDL (migration 0011), outside the ORM metadata.
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE document_search_fts "
            "ADD COLUMN tenant_id VARCHAR NOT NULL DEFAULT 'default'"
        )
        op.execute(
            "ALTER TABLE document_search_fts "
            "ADD COLUMN owner_user_id VARCHAR NOT NULL DEFAULT 'default'"
        )
        op.execute(
            "CREATE INDEX ix_document_search_fts_tenant_id "
            "ON document_search_fts (tenant_id)"
        )
        op.execute(
            "CREATE INDEX ix_document_search_fts_owner_user_id "
            "ON document_search_fts (owner_user_id)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_document_search_fts_owner_user_id")
        op.execute("DROP INDEX IF EXISTS ix_document_search_fts_tenant_id")
        op.execute("ALTER TABLE document_search_fts DROP COLUMN owner_user_id")
        op.execute("ALTER TABLE document_search_fts DROP COLUMN tenant_id")

    for table in _TABLES:
        op.drop_index(_index_name(table, "owner_user_id"), table_name=table)
        op.drop_index(_index_name(table, "tenant_id"), table_name=table)
        op.drop_column(table, "owner_user_id")
        op.drop_column(table, "tenant_id")
