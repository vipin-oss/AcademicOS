"""Application port: the document-content search projection store (M27).

A narrow, derived-data store: content rows are a searchable projection of
the extracted-text blob (the blob stays authoritative). The application
layer depends only on this abstraction; infrastructure provides the SQL
implementation. ``None``-safe: a feature that does not wire a store simply
skips content projection writes (degraded, documented behavior).
"""
from __future__ import annotations

import abc


class DocumentContentStore(abc.ABC):
    @abc.abstractmethod
    def upsert(
        self,
        *,
        object_id: str,
        version: int,
        content_text: str,
        source_item_id: str,
        content_hash: str | None = None,
    ) -> None:
        """Write/replace the content projection for ``object_id``.

        Idempotent: the row is keyed by ``object_id``; a re-index overwrites
        it. The caller owns the transaction. ``content_hash`` is the sha256
        of the NORMALIZED content (content-change authority); None for
        legacy writers until rebuild backfills it.
        """

    @abc.abstractmethod
    def delete(self, object_id: str) -> None:
        """Remove the content projection (idempotent; missing rows are ignored)."""

    @abc.abstractmethod
    def get_content(self, object_id: str) -> str | None:
        """The stored content text for ``object_id`` (``None`` when absent).

        Read seam for consumers that need the projection without a linked
        intake item (e.g. direct-upload documents in the annotation
        service's extracted-text fallback).
        """

    @abc.abstractmethod
    def get_content_projection(self, object_id: str) -> dict | None:
        """The full content projection row for ``object_id``, or ``None``.

        Returns ``{"content_text", "content_hash", "source_item_id"}`` —
        the seam the outbox applier uses to decide whether chunk
        regeneration is necessary.
        """

    @abc.abstractmethod
    def set_content_hash(self, object_id: str, content_hash: str) -> None:
        """Backfill the normalized-content hash on an existing row."""
