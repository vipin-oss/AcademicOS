"""Semantic index repository port (Sprint-5 M2 — Global Search).

Interface only — no implementation, no framework. Concrete adapters
(``FakeVectorRepository`` — the reference implementation, and
``QdrantVectorRepository``) persist the deterministic ``VectorDocument``
projection.

Contract notes (mirrors the lexical ``SearchRepository``):

- The index is a **derived projection**; objects and their version
  snapshots remain authoritative.
- ``upsert`` must be version-aware: a document older than the stored one
  never overwrites it.
- ``delete`` is idempotent; ``clear`` empties the whole store (the rebuild
  path reconstructs it from durable state).
- ``search`` returns nearest neighbours by cosine similarity, ordered by
  similarity with deterministic ``object_id`` tie-breaks; ``limit`` bounds
  the result.
"""
from __future__ import annotations

import abc
from collections.abc import Sequence

from app.domain.value_objects.vector import VectorDocument


class VectorRepository(abc.ABC):
    @abc.abstractmethod
    def upsert(self, document: VectorDocument) -> None:
        """Insert or replace the projection for ``document.object_id``.

        Version-aware: the stored document is replaced only when
        ``document.version`` is not older than the stored version.
        """

    @abc.abstractmethod
    def delete(self, object_id: str) -> None:
        """Remove the projection for ``object_id`` (idempotent)."""

    @abc.abstractmethod
    def search(
        self, vector: Sequence[float], *, limit: int = 50
    ) -> list[VectorDocument]:
        """Nearest neighbours by cosine similarity, bounded by ``limit``.

        Deterministic ordering: similarity desc, ``object_id`` asc.
        """

    @abc.abstractmethod
    def clear(self) -> None:
        """Remove every projection (used by the rebuild path)."""
