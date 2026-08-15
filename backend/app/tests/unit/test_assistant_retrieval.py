"""Unit tests for the Assistant Retrieval Service (Sprint-6 M1 Phase 1).

Merges hybrid search + graph runtime deterministically: duplicates are
eliminated, provenance is preserved (search / graph / both), ordering is
stable, the existing R4 permission filtering holds for BOTH legs, and the
result is bounded by configurable limits.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.assistant_retrieval import AssistantRetrievalService
from app.application.services.graph_runtime import GraphRuntimeService
from app.application.services.outbox import to_outbox_row
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.vector import VectorDocument
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.embedding.hashing_embedder import HashingEmbedder
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.persistence.mapper import SnapshotMapper
from app.infrastructure.persistence.search_mapping import (
    search_text,
    to_search_document,
)
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.repositories.sqlalchemy_search_repository import (
    SQLAlchemySearchRepository,
)
from app.infrastructure.search.index_applier import SearchIndexApplier
from app.infrastructure.vector_db.fake import FakeVectorRepository


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def repo(db) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


def _save_with_events(repo: SQLAlchemyObjectRepository, obj: UniversalObject) -> None:
    events = obj.pop_domain_events()
    repo.save(obj, outbox_events=[to_outbox_row(event) for event in events])


def _seed(db, repo, *objects: UniversalObject) -> tuple[FakeVectorRepository, HashingEmbedder]:
    """Index objects into both projections (lexical via relay, semantic via
    the same deterministic mapping the applier uses)."""
    embedder = HashingEmbedder()
    vectors = FakeVectorRepository()
    for obj in objects:
        _save_with_events(repo, obj)
    SearchIndexApplier(db).apply_pending()
    for obj in objects:
        snap = SnapshotMapper.to_snapshot(obj)
        doc = to_search_document(snap)
        vectors.upsert(
            VectorDocument(
                object_id=doc.object_id,
                object_type=doc.object_type,
                title=doc.title,
                metadata_text=doc.metadata_text,
                version=doc.version,
                vector=tuple(embedder.embed(search_text(snap))),
            )
        )
    return vectors, embedder


def _service(db, repo, vectors, embedder) -> AssistantRetrievalService:
    search = SearchObjectsUseCase(
        SQLAlchemySearchRepository(db),
        repo,
        ObjectPermissionEvaluator(),
        vector_repository=vectors,
        embedder=embedder,
    )
    graph = GraphRuntimeService(repo, ObjectPermissionEvaluator())
    return AssistantRetrievalService(search, graph)


def _user(obj_id: str = "obj:user:alice-0001") -> UniversalObject:
    return UniversalObject.create(
        ObjectType.USER, "alice", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId(obj_id),
    )


def _secret_user() -> UniversalObject:
    return UniversalObject.create(
        ObjectType.USER, "secret", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:bob-0002"),
    )


# ------------------------------------------------------------------ merging


def test_merges_search_and_graph_sources(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    related = UniversalObject.create(ObjectType.RESEARCH_PROJECT, "Project Notes", created_by="f:1")
    doc.add_relationship(related.id, RelationshipKind.BELONGS_TO, actor="f:1")
    vectors, embedder = _seed(db, repo, doc, related)
    service = _service(db, repo, vectors, embedder)

    result = service.retrieve("quantum", _user(), search_limit=1)
    assert any(item.sources == ("search",) for item in result.items)
    assert any(item.sources == ("graph",) for item in result.items)
    assert result.search_count >= 1
    assert result.graph_count >= 1


def test_duplicates_are_eliminated_and_upgraded(db, repo):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Paper", created_by="f:1")
    # The graph anchor is the top search hit itself: BFS includes the root's
    # neighbours only, so create a self-referencing neighbour scenario where
    # a document appears in BOTH the search hits and the graph legs.
    related = UniversalObject.create(ObjectType.DOCUMENT, "Related Notes", created_by="f:1")
    doc.add_relationship(related.id, RelationshipKind.BELONGS_TO, actor="f:1")
    related.add_relationship(doc.id, RelationshipKind.BELONGS_TO, actor="f:1")
    vectors, embedder = _seed(db, repo, doc, related)
    service = _service(db, repo, vectors, embedder)

    result = service.retrieve("quantum", _user())
    ids = [item.object_id for item in result.items]
    assert len(ids) == len(set(ids))  # no duplicates
    both = [item for item in result.items if item.sources == ("search", "graph")]
    assert len(both) >= 1  # the overlap got upgraded, not duplicated


def test_search_hits_ordered_before_graph_only_items(db, repo):
    doc_a = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Alpha", created_by="f:1")
    doc_b = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Beta", created_by="f:1")
    neighbor = UniversalObject.create(ObjectType.DOCUMENT, "Neighbor Notes", created_by="f:1")
    doc_a.add_relationship(neighbor.id, RelationshipKind.BELONGS_TO, actor="f:1")
    vectors, embedder = _seed(db, repo, doc_a, doc_b, neighbor)
    service = _service(db, repo, vectors, embedder)

    result = service.retrieve("quantum", _user(), search_limit=2, graph_anchors=2)
    graph_only = [item for item in result.items if item.sources == ("graph",)]
    # All search hits precede graph-only items.
    search_positions = [result.items.index(i) for i in result.items if "search" in i.sources]
    graph_positions = [result.items.index(i) for i in result.items if i.sources == ("graph",)]
    if search_positions and graph_positions:
        assert max(search_positions) < min(graph_positions)
    assert graph_only  # the neighbour is present via the graph leg


def test_deterministic_ordering_across_runs(db, repo):
    docs = [
        UniversalObject.create(ObjectType.DOCUMENT, f"Quantum {name}", created_by="f:1")
        for name in ("Alpha", "Beta", "Gamma")
    ]
    vectors, embedder = _seed(db, repo, *docs)
    service = _service(db, repo, vectors, embedder)

    first = [(i.object_id, i.sources, i.score) for i in service.retrieve("quantum", _user()).items]
    second = [(i.object_id, i.sources, i.score) for i in service.retrieve("quantum", _user()).items]
    assert first == second


def test_max_results_bounds_the_merged_list(db, repo):
    docs = [
        UniversalObject.create(ObjectType.DOCUMENT, f"Quantum Doc {i}", created_by="f:1")
        for i in range(6)
    ]
    vectors, embedder = _seed(db, repo, *docs)
    service = _service(db, repo, vectors, embedder)

    result = service.retrieve("quantum", _user(), max_results=3)
    assert len(result.items) == 3


# ------------------------------------------------------------- permissions


def test_restricted_objects_never_retrieved(db, repo):
    public = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Public", created_by="f:1")
    secret = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Secret", created_by="f:2")
    secret.set_metadata(
        MetadataEntry(
            "acl.readers", json.dumps(["obj:user:bob-0002"]),
            MetadataLayer.L1_SYSTEM, Provenance.SYSTEM,
        ),
        actor="system",
    )
    vectors, embedder = _seed(db, repo, public, secret)
    service = _service(db, repo, vectors, embedder)

    alice = _user()
    result = service.retrieve("quantum", alice)
    assert all("Secret" not in item.title for item in result.items)  # no leak

    bob = _secret_user()
    result_bob = service.retrieve("quantum", bob)
    assert any("Secret" in item.title for item in result_bob.items)


def test_graph_leg_respects_permissions(db, repo):
    """A restricted neighbour is excluded by the graph runtime's pre-filter."""
    owner = UniversalObject.create(ObjectType.DOCUMENT, "Owner Doc", created_by="f:1")
    restricted_neighbor = UniversalObject.create(
        ObjectType.DOCUMENT, "Restricted Neighbor", created_by="f:2"
    )
    restricted_neighbor.set_metadata(
        MetadataEntry(
            "acl.readers", json.dumps(["obj:user:bob-0002"]),
            MetadataLayer.L1_SYSTEM, Provenance.SYSTEM,
        ),
        actor="system",
    )
    owner.add_relationship(restricted_neighbor.id, RelationshipKind.BELONGS_TO, actor="f:1")
    vectors, embedder = _seed(db, repo, owner, restricted_neighbor)
    service = _service(db, repo, vectors, embedder)

    result = service.retrieve("owner", _user())
    assert all("Restricted Neighbor" not in item.title for item in result.items)
