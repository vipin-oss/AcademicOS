"""Unit tests for the semantic projection (Sprint-5 M2 Phase 2).

The fake repository is the REFERENCE implementation: version-aware upsert,
idempotent delete, deterministic cosine search, and clear() for the
rebuild path — the contract the Qdrant adapter must match.
"""
from __future__ import annotations

import pytest

from app.domain.value_objects.vector import VectorDocument
from app.infrastructure.vector_db.fake import FakeVectorRepository


def _doc(
    object_id: str,
    *,
    version: int = 1,
    title: str = "T",
    vector: tuple[float, ...] | None = None,
) -> VectorDocument:
    return VectorDocument(
        object_id=object_id,
        object_type="document",
        title=title,
        metadata_text="",
        version=version,
        vector=vector or (1.0, 0.0, 0.0, 0.0),
    )


def test_upsert_then_search_returns_document():
    repo = FakeVectorRepository()
    repo.upsert(_doc("obj:document:A", title="Alpha", vector=(1.0, 0.0, 0.0, 0.0)))
    hits = repo.search((1.0, 0.0, 0.0, 0.0), limit=10)
    assert [h.object_id for h in hits] == ["obj:document:A"]
    assert hits[0].title == "Alpha"
    assert hits[0].version == 1


def test_delete_removes_and_is_idempotent():
    repo = FakeVectorRepository()
    repo.upsert(_doc("obj:document:A"))
    repo.delete("obj:document:A")
    assert repo.search((1.0, 0.0, 0.0, 0.0)) == []
    repo.delete("obj:document:A")  # no-op, no error
    assert len(repo) == 0


def test_overwrite_replaces_newer_version():
    repo = FakeVectorRepository()
    repo.upsert(_doc("obj:document:A", version=1, title="old"))
    repo.upsert(_doc("obj:document:A", version=2, title="new"))
    hits = repo.search((1.0, 0.0, 0.0, 0.0))
    assert len(hits) == 1  # one projection, not a history
    assert hits[0].title == "new"
    assert hits[0].version == 2


def test_version_guard_rejects_stale_overwrite():
    repo = FakeVectorRepository()
    repo.upsert(_doc("obj:document:A", version=5, title="current"))
    repo.upsert(_doc("obj:document:A", version=3, title="stale"))
    hits = repo.search((1.0, 0.0, 0.0, 0.0))
    assert len(hits) == 1
    assert hits[0].title == "current"
    assert hits[0].version == 5


def test_reupsert_is_idempotent():
    repo = FakeVectorRepository()
    doc = _doc("obj:document:A", version=1)
    repo.upsert(doc)
    repo.upsert(doc)
    assert len(repo) == 1


def test_search_ranks_by_cosine_similarity():
    repo = FakeVectorRepository()
    repo.upsert(_doc("obj:document:A", vector=(1.0, 0.0, 0.0, 0.0)))
    repo.upsert(_doc("obj:document:B", vector=(0.9, 0.1, 0.0, 0.0)))
    repo.upsert(_doc("obj:document:C", vector=(0.0, 1.0, 0.0, 0.0)))
    hits = repo.search((1.0, 0.0, 0.0, 0.0))
    assert [h.object_id for h in hits] == ["obj:document:A", "obj:document:B", "obj:document:C"]


def test_search_deterministic_ties_by_object_id():
    repo = FakeVectorRepository()
    # Equal similarity: order must fall back to object_id, never to
    # insertion order.
    repo.upsert(_doc("obj:document:Z", vector=(1.0, 0.0, 0.0, 0.0)))
    repo.upsert(_doc("obj:document:A", vector=(1.0, 0.0, 0.0, 0.0)))
    repo.upsert(_doc("obj:document:M", vector=(1.0, 0.0, 0.0, 0.0)))
    hits = repo.search((1.0, 0.0, 0.0, 0.0))
    assert [h.object_id for h in hits] == [
        "obj:document:A",
        "obj:document:M",
        "obj:document:Z",
    ]


def test_search_limit():
    repo = FakeVectorRepository()
    for i in range(10):
        repo.upsert(_doc(f"obj:document:{i:02d}", vector=(1.0, 0.0, 0.0, 0.0)))
    assert len(repo.search((1.0, 0.0, 0.0, 0.0), limit=3)) == 3


def test_clear_empties_for_rebuild():
    repo = FakeVectorRepository()
    repo.upsert(_doc("obj:document:A"))
    repo.upsert(_doc("obj:document:B"))
    repo.clear()
    assert len(repo) == 0
    # Rebuild compatibility: the store accepts fresh upserts afterwards.
    repo.upsert(_doc("obj:document:A", version=2))
    assert len(repo.search((1.0, 0.0, 0.0, 0.0))) == 1


def test_dimension_mismatch_raises():
    repo = FakeVectorRepository()
    repo.upsert(_doc("obj:document:A", vector=(1.0, 0.0)))
    with pytest.raises(ValueError):
        repo.search((1.0, 0.0, 0.0, 0.0))
