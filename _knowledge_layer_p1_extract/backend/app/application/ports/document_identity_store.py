"""Application port: the document-identity registry store (P1).

A narrow derived-data store keyed by ``content_hash`` (sha256 of the
NORMALIZED extracted text). The caller owns the transaction (same
convention as the content/chunk stores). All methods are deterministic
and idempotent; the canonical representative is always the smallest
object_id among the documents sharing the hash.
"""
from __future__ import annotations

import abc


class DocumentIdentityStore(abc.ABC):
    @abc.abstractmethod
    def sync_document(self, *, content_hash: str, object_id: str) -> None:
        """Record one document under its content identity.

        Creates the registry row when the hash is new (canonical = the
        document), or re-evaluates the canonical (smallest object_id) and
        recomputes the count. Idempotent.
        """

    @abc.abstractmethod
    def remove_document(self, *, content_hash: str, object_id: str) -> None:
        """Remove one document from the identity group.

        Deletes the registry row when no documents remain under the hash;
        otherwise recomputes the canonical (smallest remaining object_id)
        and the count. Idempotent.
        """

    @abc.abstractmethod
    def canonical_for(self, content_hash: str) -> str | None:
        """The canonical document id for a content hash (``None`` if none)."""

    @abc.abstractmethod
    def group(self, content_hash: str) -> list[str]:
        """All document ids sharing the content hash (deterministic order)."""

    @abc.abstractmethod
    def recompute(self, entries: list[dict]) -> None:
        """Rebuild the whole registry from content projections.

        ``entries`` = [{"content_hash", "object_id"}, ...]; the canonical
        per hash is the smallest object_id (deterministic). Delete-all +
        re-insert in the caller's transaction.
        """

    @abc.abstractmethod
    def duplicate_count(self) -> int:
        """Number of documents that are NOT their group's canonical (i.e.,
        duplicate/alias uploads)."""
