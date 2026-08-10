"""SQL implementation of the document-content projection store (M27).

``document_contents`` rows are keyed by the owning DOCUMENT object id;
upsert is a select-then-insert/update (dialect-agnostic, mirrors the
codebase's explicit write style — no ON CONFLICT dependency). No commits
here — the caller owns the transaction, exactly like the object
repository's write convention.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.application.ports.document_content_store import DocumentContentStore
from app.infrastructure.db.models.document_content_model import DocumentContentModel


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


class SQLDocumentContentStore(DocumentContentStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(
        self, *, object_id: str, version: int, content_text: str, source_item_id: str
    ) -> None:
        row = self._session.get(DocumentContentModel, object_id)
        if row is None:
            self._session.add(
                DocumentContentModel(
                    object_id=object_id,
                    version=version,
                    content_text=content_text,
                    source_item_id=source_item_id,
                    created_at=_utcnow_iso(),
                )
            )
        else:
            row.version = version
            row.content_text = content_text
            row.source_item_id = source_item_id

    def delete(self, object_id: str) -> None:
        self._session.execute(
            delete(DocumentContentModel).where(
                DocumentContentModel.object_id == object_id
            )
        )
