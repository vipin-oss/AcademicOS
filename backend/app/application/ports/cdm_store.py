"""Application port: the L1 CDM block store (Blueprint §11).

The single seam between the structured-document block lifecycle (application)
and durable storage (infrastructure). The port carries domain ``CdmBlock``
objects, never ORM models. ``block_id`` is the idempotency key. The caller
owns the transaction.
"""

from __future__ import annotations

import abc

from app.domain.value_objects.cdm import CdmBlock


class CdmStore(abc.ABC):
    @abc.abstractmethod
    def replace_for_document(
        self, document_id: str, version: int, blocks: list[CdmBlock]
    ) -> None:
        """Replace the block set for one document version (delete-then-insert
        in the caller's tx). Idempotent by block_id for identical inputs."""

    @abc.abstractmethod
    def by_document(self, document_id: str, version: int | None = None) -> list[CdmBlock]:
        """Blocks of one document, in reading order (``order`` ascending)."""

    @abc.abstractmethod
    def delete_by_document(self, document_id: str) -> None:
        """Remove all blocks of one document (idempotent)."""

    @abc.abstractmethod
    def count(self, document_id: str) -> int:
        """Number of block rows for one document."""
