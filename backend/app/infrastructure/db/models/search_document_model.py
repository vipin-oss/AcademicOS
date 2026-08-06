"""SQLAlchemy model for the ``search_documents`` projection table (Sprint-5 M1).

The persistent search index: one deterministic row per object's current
searchable state, written ONLY by the outbox consumer (``SearchIndexApplier``)
and rebuilt from version snapshots. Plain columns — no FTS extension, no
vector column: the roadmap-approved search surface (exact object type,
exact title, literal-substring full-text over title + metadata text) is
served by the existing persistence layer.

Design notes:

- ``object_id`` is the primary key: replaying the outbox can never produce
  duplicate index rows (upsert semantics).
- ``version`` is the object version the row reflects; upserts are
  version-aware so a stale projection never overwrites a newer one.
- No FK to ``objects``: the index is eventually consistent and derived;
  deletion is driven by the relay, and ``rebuild`` clears the table.
"""
from __future__ import annotations

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base


class SearchDocumentModel(Base):
    __tablename__ = "search_documents"
    __table_args__ = (
        # Exact object-type filtering (the only indexed exact-match column).
        Index("ix_search_documents_object_type", "object_type"),
    )

    object_id: Mapped[str] = mapped_column(String, primary_key=True)
    object_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    metadata_text: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
