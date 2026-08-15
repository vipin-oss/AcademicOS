"""Application port: document revision store (V3 M11, ADR-058)."""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentRevision:
    id: str
    document_id: str
    revision_version: int
    file_name: str
    content_hash: str
    mime_type: str
    file_size: int
    storage_key: str
    quarantined: bool = False
    quarantine_reason: str | None = None
    created_at: str = ""


class DocumentRevisionStore(abc.ABC):
    @abc.abstractmethod
    def add(self, revision: DocumentRevision) -> DocumentRevision:
        """Record one immutable revision (idempotent by id)."""

    @abc.abstractmethod
    def next_version(self, document_id: str) -> int:
        """The next revision version for a document (1 for a new document)."""

    @abc.abstractmethod
    def for_document(self, document_id: str) -> list[DocumentRevision]:
        """All revisions of a document, oldest first."""
