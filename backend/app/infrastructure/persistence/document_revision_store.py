"""SQL implementation of the document revision store (V3 M11, ADR-058)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.ports.document_revision_store import (
    DocumentRevision,
    DocumentRevisionStore,
)
from app.infrastructure.db.models.document_revision_model import DocumentRevisionModel


class SQLDocumentRevisionStore(DocumentRevisionStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, revision: DocumentRevision) -> DocumentRevision:
        existing = self._session.execute(
            select(DocumentRevisionModel).where(DocumentRevisionModel.id == revision.id)
        ).scalars().first()
        if existing is not None:
            return revision  # idempotent
        self._session.add(
            DocumentRevisionModel(
                id=revision.id,
                document_id=revision.document_id,
                revision_version=revision.revision_version,
                file_name=revision.file_name,
                content_hash=revision.content_hash,
                mime_type=revision.mime_type,
                file_size=revision.file_size,
                storage_key=revision.storage_key,
                quarantined=1 if revision.quarantined else 0,
                quarantine_reason=revision.quarantine_reason,
                created_at=revision.created_at,
            )
        )
        return revision

    def next_version(self, document_id: str) -> int:
        current = self._session.execute(
            select(func.max(DocumentRevisionModel.revision_version)).where(
                DocumentRevisionModel.document_id == document_id
            )
        ).scalar()
        return (current or 0) + 1

    def for_document(self, document_id: str) -> list[DocumentRevision]:
        rows = self._session.execute(
            select(DocumentRevisionModel)
            .where(DocumentRevisionModel.document_id == document_id)
            .order_by(DocumentRevisionModel.revision_version)
        ).scalars().all()
        return [_from_model(r) for r in rows]


def _from_model(row: DocumentRevisionModel) -> DocumentRevision:
    return DocumentRevision(
        id=row.id,
        document_id=row.document_id,
        revision_version=row.revision_version,
        file_name=row.file_name,
        content_hash=row.content_hash,
        mime_type=row.mime_type,
        file_size=row.file_size,
        storage_key=row.storage_key,
        quarantined=bool(row.quarantined),
        quarantine_reason=row.quarantine_reason,
        created_at=row.created_at,
    )
