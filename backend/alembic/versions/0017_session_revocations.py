"""session_revocations — durable token revocation denylist (V3 M9)

Revision ID: 0017_session_revocations
Revises: 0016_typed_claims
Create Date: 2026-08-15

V3 Milestone M9 (ADR-056 "revocation"): a durable denylist of revoked token
``jti``s. Logout writes a row; authentication rejects a token whose ``jti`` is
present and not yet expired. Rows are pruned past the token's absolute expiry
so the table stays bounded. Additive only.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0017_session_revocations"
down_revision = "0016_typed_claims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_revocations",
        sa.Column("jti", sa.String(), nullable=False),
        sa.Column("expires_at", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False, server_default="default"),
        sa.Column("owner_user_id", sa.String(), nullable=False, server_default="default"),
        sa.PrimaryKeyConstraint("jti"),
    )
    op.create_index("ix_session_revocations_tenant_id", "session_revocations", ["tenant_id"])
    op.create_index("ix_session_revocations_owner_user_id", "session_revocations", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_session_revocations_owner_user_id", table_name="session_revocations")
    op.drop_index("ix_session_revocations_tenant_id", table_name="session_revocations")
    op.drop_table("session_revocations")
