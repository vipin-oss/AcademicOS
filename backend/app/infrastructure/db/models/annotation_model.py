"""SQLAlchemy model for the ``document_annotations`` table (Sprint M10).

One row per user annotation attached to a document: highlights (a rect
list on one page), notes (page-anchored text) and bookmarks (page
marks). ``payload`` is JSONB on PostgreSQL / JSON elsewhere (the system
doctrine); ``annotation_id`` is the unique idempotency key. Unlike the
append-only audit tables, annotations are mutable user content — update
and delete are supported.
"""
from __future__ import annotations

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base, TenantStampMixin
from app.infrastructure.db.types import JSONBType


class DocumentAnnotationModel(TenantStampMixin, Base):
    __tablename__ = "document_annotations"
    __table_args__ = (
        # Viewer read: one document's annotations, page-ordered.
        Index(
            "ix_document_annotations_document_id_page",
            "document_id",
            "page",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    annotation_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    document_id: Mapped[str] = mapped_column(String, nullable=False)
    annotation_type: Mapped[str] = mapped_column(String, nullable=False)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str | None] = mapped_column(String, nullable=True)
