"""temporal graph + evidence foreign keys (V3 M17)

Revision ID: 0024_temporal_graph_identity
Revises: 0023_user_profiles
Create Date: 2026-08-15

V3 Milestone M17 (ADR-064):

1. Validity intervals on relationships: add ``valid_from`` / ``valid_to``
   (nullable ISO-8601 strings) to ``object_relationships`` — open interval
   when absent.
2. Evidence foreign keys: ``claims.source_document_id`` and
   ``claim_spans.source_id`` gain ``ON DELETE RESTRICT`` foreign keys to
   ``objects(id)``, so deleting a document that still has claims/spans is
   REFUSED (never cascades evidence away). PostgreSQL-only: SQLite runs with
   FK enforcement off (PRAGMA), and the tests exercise the same DDL without
   enforcement — the production guarantee is the Postgres constraint.
"""
from __future__ import annotations

from alembic import op

revision = "0024_temporal_graph_identity"
down_revision = "0023_user_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("object_relationships", sa_column("valid_from"))
    op.add_column("object_relationships", sa_column("valid_to"))
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE claims ADD CONSTRAINT fk_claims_source_document "
            "FOREIGN KEY (source_document_id) REFERENCES objects(id) ON DELETE RESTRICT"
        )
        op.execute(
            "ALTER TABLE claim_spans ADD CONSTRAINT fk_claim_spans_source "
            "FOREIGN KEY (source_id) REFERENCES objects(id) ON DELETE RESTRICT"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE claim_spans DROP CONSTRAINT fk_claim_spans_source")
        op.execute("ALTER TABLE claims DROP CONSTRAINT fk_claims_source_document")
    op.drop_column("object_relationships", "valid_to")
    op.drop_column("object_relationships", "valid_from")


def sa_column(name: str):
    import sqlalchemy as sa

    return sa.Column(name, sa.String(), nullable=True)
