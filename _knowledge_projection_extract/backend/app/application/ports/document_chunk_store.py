"""Application port: the document-chunk projection store (P0).

A narrow, derived-data store mirroring ``DocumentContentStore``: chunk rows
are a deterministic segmentation of the extracted-content projection and
are keyed by (document_id, chunk_index). The caller owns the transaction
(exactly like the object repository / content store convention). The port
accepts the chunking service's ``Chunk`` objects, never ORM models.
"""
from __future__ import annotations

import abc

from app.application.services.document_chunking import Chunk


class DocumentChunkStore(abc.ABC):
    @abc.abstractmethod
    def replace(
        self,
        *,
        document_id: str,
        version: int,
        source_item_id: str | None,
        chunks: list[Chunk],
    ) -> None:
        """Replace the chunk set for one document.

        Delete-then-insert for that document inside the caller's
        transaction: a document can never have two versions of a chunk
        coexist (PK (document_id, chunk_index)). Idempotent: re-running
        with the same input produces the same final rows.
        """

    @abc.abstractmethod
    def delete_by_document(self, document_id: str) -> None:
        """Remove all chunks of one document (idempotent)."""

    @abc.abstractmethod
    def delete_all(self) -> None:
        """Remove every chunk row (rebuild path)."""

    @abc.abstractmethod
    def count(self, document_id: str) -> int:
        """Number of chunk rows for one document."""

    @abc.abstractmethod
    def by_document(self, document_id: str) -> list[dict]:
        """Chunk rows of one document as plain dicts (tests/equivalence)."""
