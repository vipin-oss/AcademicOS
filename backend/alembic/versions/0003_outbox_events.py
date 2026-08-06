"""outbox_events table

Revision ID: 0003_outbox_events
Revises: 0002_object_relationships
Create Date: 2026-08-06

Sprint-4 Milestone A — durable, replayable domain-event storage. Rows are
appended in the same transaction as the aggregate save that produced the
events; ``event_id`` is the unique idempotency key (the aggregate's
``DomainEvent.event_id`` UUID), and ``delivered_at`` marks relay delivery.

Downgrade drops the table (events are replays of committed state — the
objects themselves are untouched).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0003_outbox_events"
down_revision = "0002_object_relationships"
branch_labels = None
depends_on = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    is_pg = _is_postgresql()
    json_type = postgresql.JSONB() if is_pg else sa.JSON()

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(), nullable=False, unique=True),
        sa.Column("aggregate_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", json_type, nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("delivered_at", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_outbox_events_delivered",
        "outbox_events",
        ["delivered_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_delivered", table_name="outbox_events")
    op.drop_table("outbox_events")
