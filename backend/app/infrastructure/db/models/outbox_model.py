"""SQLAlchemy model for the ``outbox_events`` table (Sprint-4 Milestone A).

Durable, replayable domain-event storage. The ``event_id`` column is the
unique idempotency key (the aggregate's ``DomainEvent.event_id`` UUID), so
re-delivering or re-committing an event never duplicates a row. Rows are
written in the SAME transaction as the aggregate save that produced them
(the repository adds them inside its write lambda) and stay until a relay
marks them delivered — a crash never loses an event that was committed.
"""
from __future__ import annotations

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base, TenantStampMixin
from app.infrastructure.db.types import JSONBType


class OutboxEventModel(TenantStampMixin, Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        # Delivery sweep: undelivered rows, oldest first.
        Index("ix_outbox_events_delivered", "delivered_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    # JSONB on PostgreSQL; JSON elsewhere (same doctrine as the objects table).
    payload: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    delivered_at: Mapped[str | None] = mapped_column(String, nullable=True)
