"""Add entity_matches table for persistent match decisions.

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-17
"""

from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entity_matches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_doc_id", sa.String(255), nullable=False, index=True),
        sa.Column("target_doc_id", sa.String(255), nullable=False, index=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("evidence", sa.Text, nullable=False),
        sa.Column("decision", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("decided_by", sa.String(255), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Unique constraint on (source, target) for idempotency
    op.create_index(
        "ix_entity_matches_source_target",
        "entity_matches",
        ["source_doc_id", "target_doc_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_entity_matches_source_target", table_name="entity_matches")
    op.drop_table("entity_matches")
