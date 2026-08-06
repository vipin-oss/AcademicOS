"""Unit tests for the Qdrant vector adapter (Sprint-5 M2 Phase 5).

Runs against the REAL in-process Qdrant emulator (``QdrantClient(":memory:")``)
— the same client code path production uses. The suite mirrors
``test_vector_repository.py`` one-to-one: the fake is the reference
implementation and the Qdrant adapter must behave identically.
"""
from __future__ import annotations

import pytest
from qdrant_client import QdrantClient

from app.domain.value_objects.vector import VectorDocument
from app.infrastructure.vector_db.collections import VectorCollectionManager
from app.infrastructure.vector_db.qdrant_vector_repository import (
    QdrantVectorRepository,
)


@pytest.fixture()
def repo():
    client = QdrantClient(":memory:")
    try:
        collection = VectorCollectionManager(client, dimensions=4).ensure()
        yield QdrantVectorRepository(client, collection)
    finally:
        client.close()


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


def test_upsert_then_search_returns_document(repo):
    repo.upsert(_doc("obj:document:A", title="Alpha", vector=(1.0, 0.0, 0.0, 0.0)))
    hits = repo.search((1.0, 0.0, 0.0, 0.0), limit=10)
    assert [h.object_id for h in hits] == ["obj:document:A"]
    assert hits[0].title == "Alpha"
    assert hits[0].version == 1
    assert len(hits[0].vector) == 4


def test_delete_removes_and_is_idempotent(repo):
    repo.upsert(_doc("obj:document:A"))
    repo.delete("obj:document:A")
    assert repo.search((1.0, 0.0, 0.0, 0.0)) == []
    repo.delete("obj:document:A")  # no-op, no error


def test_overwrite_replaces_newer_version(repo):
    repo.upsert(_doc("obj:document:A", version=1, title="old"))
    repo.upsert(_doc("obj:document:A", version=2, title="new"))
    hits = repo.search((1.0, 0.0, 0.0, 0.0))
    assert len(hits) == 1
    assert hits[0].title == "new"
    assert hits[0].version == 2


def test_version_guard_rejects_stale_overwrite(repo):
    repo.upsert(_doc("obj:document:A", version=5, title="current"))
    repo.upsert(_doc("obj:document:A", version=3, title="stale"))
    hits = repo.search((1.0, 0.0, 0.0, 0.0))
    assert len(hits) == 1
    assert hits[0].title == "current"
    assert hits[0].version == 5


def test_reupsert_is_idempotent(repo):
    doc = _doc("obj:document:A", version=1)
    repo.upsert(doc)
    repo.upsert(doc)
    assert len(repo.search((1.0, 0.0, 0.0, 0.0))) == 1


def test_search_ranks_by_cosine_similarity(repo):
    repo.upsert(_doc("obj:document:A", vector=(1.0, 0.0, 0.0, 0.0)))
    repo.upsert(_doc("obj:document:B", vector=(0.9, 0.1, 0.0, 0.0)))
    repo.upsert(_doc("obj:document:C", vector=(0.0, 1.0, 0.0, 0.0)))
    hits = repo.search((1.0, 0.0, 0.0, 0.0))
    assert [h.object_id for h in hits] == [
        "obj:document:A",
        "obj:document:B",
        "obj:document:C",
    ]


def test_search_deterministic_ties_by_object_id(repo):
    repo.upsert(_doc("obj:document:Z", vector=(1.0, 0.0, 0.0, 0.0)))
    repo.upsert(_doc("obj:document:A", vector=(1.0, 0.0, 0.0, 0.0)))
    repo.upsert(_doc("obj:document:M", vector=(1.0, 0.0, 0.0, 0.0)))
    hits = repo.search((1.0, 0.0, 0.0, 0.0))
    assert [h.object_id for h in hits] == [
        "obj:document:A",
        "obj:document:M",
        "obj:document:Z",
    ]


def test_search_limit(repo):
    for i in range(10):
        repo.upsert(_doc(f"obj:document:{i:02d}", vector=(1.0, 0.0, 0.0, 0.0)))
    assert len(repo.search((1.0, 0.0, 0.0, 0.0), limit=3)) == 3


def test_clear_empties_for_rebuild(repo):
    repo.upsert(_doc("obj:document:A"))
    repo.upsert(_doc("obj:document:B"))
    repo.clear()
    assert repo.search((1.0, 0.0, 0.0, 0.0)) == []
    repo.upsert(_doc("obj:document:A", version=2))  # rebuild compatibility
    assert len(repo.search((1.0, 0.0, 0.0, 0.0))) == 1


def test_collection_manager_is_idempotent():
    client = QdrantClient(":memory:")
    try:
        manager = VectorCollectionManager(client, dimensions=4)
        first = manager.ensure()
        second = manager.ensure()
        assert first == "search_objects_active"
        assert second == "search_objects_active"
        assert client.collection_exists("search_objects_v1")
    finally:
        client.close()
