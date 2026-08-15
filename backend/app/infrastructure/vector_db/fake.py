"""In-memory VectorRepository — the reference implementation (Sprint-5 M2).

Deterministic, dependency-free, and the behaviour the Qdrant adapter must
match: version-aware upserts (stale never overwrites), idempotent delete,
cosine nearest-neighbour search with deterministic ``object_id`` ties, and
``clear`` for the rebuild path. Used by CI and by the default unit/integration
suites; the Qdrant adapter implements the same interface for production.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

from app.domain.repositories.vector_repository import VectorRepository
from app.domain.value_objects.vector import VectorDocument


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Vector dimension mismatch.")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class FakeVectorRepository(VectorRepository):
    """In-memory reference implementation of the semantic projection."""

    def __init__(self) -> None:
        self._documents: dict[str, VectorDocument] = {}

    def upsert(self, document: VectorDocument) -> None:
        existing = self._documents.get(document.object_id)
        if existing is not None and existing.version > document.version:
            return  # version guard: a stale projection never overwrites
        self._documents[document.object_id] = document

    def delete(self, object_id: str) -> None:
        self._documents.pop(object_id, None)

    def search(
        self, vector: Sequence[float], *, limit: int = 50
    ) -> list[VectorDocument]:
        ranked = sorted(
            self._documents.values(),
            key=lambda doc: (-_cosine(vector, doc.vector), doc.object_id),
        )
        return ranked[:limit]

    def clear(self) -> None:
        self._documents.clear()

    def __len__(self) -> int:
        return len(self._documents)
