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
        self,
        *,
        object_id: str,
        version: int,
        content_text: str,
        source_item_id: str,
        content_hash: str | None = None,
    ) -> None:
        row = self._session.get(DocumentContentModel, object_id)
        if row is None:
            self._session.add(
                DocumentContentModel(
                    object_id=object_id,
                    version=version,
                    content_text=content_text,
                    content_hash=content_hash,
                    source_item_id=source_item_id,
                    created_at=_utcnow_iso(),
                )
            )
        else:
            row.version = version
            row.content_text = content_text
            row.source_item_id = source_item_id
            if content_hash is not None:
                row.content_hash = content_hash

    def delete(self, object_id: str) -> None:
        self._session.execute(
            delete(DocumentContentModel).where(
                DocumentContentModel.object_id == object_id
            )
        )

    def get_content(self, object_id: str) -> str | None:
        """The content text for ``object_id`` (``None`` when no row)."""
        row = self._session.get(DocumentContentModel, object_id)
        if row is None:
            return None
        return row.content_text

    def get_content_projection(self, object_id: str) -> dict | None:
        """The content projection row (text, hash, provenance) or ``None``."""
        row = self._session.get(DocumentContentModel, object_id)
        if row is None:
            return None
        return {
            "content_text": row.content_text,
            "content_hash": row.content_hash,
            "source_item_id": row.source_item_id,
        }

    def set_content_hash(self, object_id: str, content_hash: str) -> None:
        """Backfill the normalized-content hash on an existing row."""
        row = self._session.get(DocumentContentModel, object_id)
        if row is not None:
            row.content_hash = content_hash
