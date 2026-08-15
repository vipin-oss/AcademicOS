"""SQL implementation of the document-chunk projection store (P0).

Mirrors ``SQLDocumentContentStore``: dialect-agnostic explicit writes, no
commits here — the caller (the outbox applier / rebuild) owns the
transaction, exactly like the object repository's write convention.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.application.ports.document_chunk_store import DocumentChunkStore
from app.application.services.document_chunking import Chunk, content_hash
from app.infrastructure.db.models.document_chunk_model import DocumentChunkModel


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


class SQLDocumentChunkStore(DocumentChunkStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace(
        self,
        *,
        document_id: str,
        version: int,
        source_item_id: str | None,
        chunks: list[Chunk],
    ) -> None:
        self._session.execute(
            delete(DocumentChunkModel).where(
                DocumentChunkModel.document_id == document_id
            )
        )
        now = _utcnow_iso()
        for index, chunk in enumerate(chunks):
            self._session.add(
                DocumentChunkModel(
                    document_id=document_id,
                    chunk_index=index,
                    content=chunk.content,
                    char_start=chunk.start,
                    char_end=chunk.end,
                    token_count=chunk.token_count,
                    content_hash=content_hash(chunk.content),
                    version=version,
                    source_item_id=source_item_id,
                    created_at=now,
                )
            )

    def delete_by_document(self, document_id: str) -> None:
        self._session.execute(
            delete(DocumentChunkModel).where(
                DocumentChunkModel.document_id == document_id
            )
        )

    def delete_all(self) -> None:
        self._session.execute(delete(DocumentChunkModel))

    def count(self, document_id: str) -> int:
        return int(
            self._session.execute(
                select(func.count())
                .select_from(DocumentChunkModel)
                .where(DocumentChunkModel.document_id == document_id)
            ).scalar_one()
        )

    def by_document(self, document_id: str) -> list[dict]:
        rows = self._session.execute(
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_id == document_id)
            .order_by(DocumentChunkModel.chunk_index)
        ).scalars().all()
        return [
            {
                "document_id": row.document_id,
                "chunk_index": row.chunk_index,
                "content": row.content,
                "char_start": row.char_start,
                "char_end": row.char_end,
                "token_count": row.token_count,
                "content_hash": row.content_hash,
                "version": row.version,
                "source_item_id": row.source_item_id,
            }
            for row in rows
        ]
