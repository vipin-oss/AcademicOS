"""Search index repository port (Sprint-5 M1 — Global Search Foundation).

Interface only — no implementation, no SQL, no framework. The concrete
adapter (``SQLAlchemySearchRepository``) persists the deterministic
``SearchDocument`` projection derived from object snapshots.

Contract notes:

- The port is write-only + query: the index is a **derived projection**.
  Objects and their version snapshots remain authoritative; ``rebuild`` is
  an operational concern of the consumer (outbox applier), not of this
  port.
- ``search`` supports only the roadmap-approved capabilities: exact
  object type, exact (case-insensitive) title, and simple full-text
  matching over title + metadata text. No ranking — results come back in
  deterministic ``object_id`` order.
- ``upsert`` must be version-aware: a document older than the stored one
  never overwrites it (the adapter enforces this atomically).
"""
from __future__ import annotations

import abc

from app.domain.value_objects.search import SearchDocument


class SearchRepository(abc.ABC):
    @abc.abstractmethod
    def upsert(self, document: SearchDocument) -> None:
        """Insert or replace the projection for ``document.object_id``.

        Version-aware: the stored row is replaced only when
        ``document.version`` is not older than the stored version.
        """

    @abc.abstractmethod
    def delete(self, object_id: str) -> None:
        """Remove the projection for ``object_id`` (idempotent)."""

    @abc.abstractmethod
    def search(
        self,
        *,
        text: str | None = None,
        object_type: str | None = None,
        title: str | None = None,
        limit: int = 50,
    ) -> list[SearchDocument]:
        """Documents matching the given criteria.

        Criteria are ANDed; at least one criterion is expected (callers
        validate). ``text`` is a literal substring match over title and
        metadata text (case-insensitive; LIKE wildcards in the input are
        treated literally). ``title`` is an exact case-insensitive match.
        Results are ordered deterministically by ``object_id``.
        """
