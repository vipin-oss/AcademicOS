"""SQLAlchemy model: ``document_revisions`` (V3 M11, ADR-058).

One immutable row per upload revision of a document. The document's content
identity is ``document_id + revision_version + content_hash``; a new upload of
the same document creates a NEW revision (superseding the old, never
overwriting history) — the explicit-revisions upgrade of M5's
``source_version`` binding (blueprint A9).

``quarantined`` records the M11 pipeline's deterministic malicious-file
decision; a quarantined revision is stored but never indexed/claimed.
"""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base, TenantStampMixin


class DocumentRevisionModel(TenantStampMixin, Base):
    __tablename__ = "document_revisions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    revision_version: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    quarantined: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
    quarantine_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
