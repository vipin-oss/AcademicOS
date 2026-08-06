"""Unit tests for hybrid search (Sprint-5 M2 Phase 3).

Lexical + semantic fusion must be deterministic, permission-filtered by
the unchanged M1 gate, and degrade to exactly the M1 behaviour whenever
the semantic layer is unavailable.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.dtos.search import (
    INDEX_SOURCE_BOTH,
    INDEX_SOURCE_LEXICAL,
    INDEX_SOURCE_SEMANTIC,
)
from app.application.services.outbox import to_outbox_row
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
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


@pytest.fixture()
def embedder() -> HashingEmbedder:
    return HashingEmbedder()


def _save_with_events(repo: SQLAlchemyObjectRepository, obj: UniversalObject) -> None:
    events = obj.pop_domain_events()
    repo.save(obj, outbox_events=[to_outbox_row(event) for event in events])


def _seed(db, repo, embedder, *objects: UniversalObject) -> FakeVectorRepository:
    """Index the given objects into BOTH projections.

    Lexical via the relay (M1 path); semantic via the deterministic
    mapping + embedder — the same text composition the applier uses, so
    Phase 4's ``rebuild == replay`` guarantee holds for these seeds.
    """
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
    return vectors


def _use_case(db, repo, vectors=None, embedder=None) -> SearchObjectsUseCase:
    return SearchObjectsUseCase(
        SQLAlchemySearchRepository(db),
        repo,
        ObjectPermissionEvaluator(),
        vector_repository=vectors,
        embedder=embedder,
    )


def _user(obj_id: str = "obj:user:alice-0001") -> UniversalObject:
    return UniversalObject.create(
        ObjectType.USER, "alice", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId(obj_id),
    )


# ---------------------------------------------------------------- fusion


def test_both_legs_fuse_with_provenance(db, repo, embedder):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Physics Notes", created_by="f:1")
    vectors = _seed(db, repo, embedder, doc)

    hits = _use_case(db, repo, vectors, embedder).execute(user=_user(), text="quantum")
    assert len(hits) == 1
    hit = hits[0]
    assert hit.object_id == str(doc.id)
    assert hit.index_source == INDEX_SOURCE_BOTH
    assert hit.score > 0
    assert hit.version == 1
    assert hit.object_type == "document"
    assert hit.title == "Quantum Physics Notes"


def test_semantic_only_hit(db, repo, embedder):
    """The lexical leg needs a literal substring; a token-overlap query can
    only be found semantically — and must still be returned."""
    doc = UniversalObject.create(
        ObjectType.DOCUMENT, "Quantum Entanglement Notes", created_by="f:1"
    )
    vectors = _seed(db, repo, embedder, doc)

    hits = _use_case(db, repo, vectors, embedder).execute(
        user=_user(), text="quantum entangled"
    )
    assert [h.object_id for h in hits] == [str(doc.id)]
    assert hits[0].index_source == INDEX_SOURCE_SEMANTIC


def test_prefix_overlap_is_a_semantic_candidate(db, repo, embedder):
    """Top-k provenance semantics: with n <= limit documents every document
    is a semantic candidate, so a lexical hit that shares no token with the
    query still reports 'both' (the semantic leg legitimately re-ranked it
    at zero similarity). Same as Qdrant's native top-k behaviour."""
    doc = UniversalObject.create(ObjectType.DOCUMENT, "History of Haryana", created_by="f:1")
    vectors = _seed(db, repo, embedder, doc)

    hits = _use_case(db, repo, vectors, embedder).execute(
        user=_user(), text="his"  # substring of 'history' -> lexical; no token overlap
    )
    assert [h.object_id for h in hits] == [str(doc.id)]
    assert hits[0].index_source == INDEX_SOURCE_BOTH


def test_fusion_is_deterministic_and_ranked(db, repo, embedder):
    docs = [
        UniversalObject.create(ObjectType.DOCUMENT, f"Quantum {name}", created_by="f:1")
        for name in ("Alpha", "Beta", "Gamma")
    ]
    vectors = _seed(db, repo, embedder, *docs)
    use_case = _use_case(db, repo, vectors, embedder)

    first = use_case.execute(user=_user(), text="quantum")
    second = use_case.execute(user=_user(), text="quantum")
    assert [(h.object_id, h.score) for h in first] == [(h.object_id, h.score) for h in second]
    # Scores are strictly ordered (RRF over equal rank positions) with
    # object_id tie-breaks — never insertion order.
    ids = [h.object_id for h in first]
    assert ids == sorted(ids)


def test_semantic_leg_respects_object_type_filter(db, repo, embedder):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Quantum Notes", created_by="f:1")
    course = UniversalObject.create(ObjectType.COURSE, "Quantum Course", created_by="f:1")
    vectors = _seed(db, repo, embedder, doc, course)

    hits = _use_case(db, repo, vectors, embedder).execute(
        user=_user(), text="quantum", object_type="course"
    )
    assert [h.object_id for h in hits] == [str(course.id)]
    assert all(h.object_type == "course" for h in hits)


def test_limit_applies_to_fused_results(db, repo, embedder):
    docs = [
        UniversalObject.create(ObjectType.DOCUMENT, f"Quantum Doc {i}", created_by="f:1")
        for i in range(5)
    ]
    vectors = _seed(db, repo, embedder, *docs)
    hits = _use_case(db, repo, vectors, embedder).execute(
        user=_user(), text="quantum", limit=2
    )
    assert len(hits) == 2


# ---------------------------------------------------- graceful degradation


def test_no_semantic_layer_is_exactly_m1(db, repo):
    """Without a vector repository/embedder the result is byte-identical
    to M1: same candidates, same (object_id) ordering, lexical provenance."""
    docs = [
        UniversalObject.create(ObjectType.DOCUMENT, f"Doc {i}", created_by="f:1")
        for i in range(3)
    ]
    _seed(db, repo, HashingEmbedder(), *docs)  # lexical only is enough

    use_case = SearchObjectsUseCase(
        SQLAlchemySearchRepository(db), repo, ObjectPermissionEvaluator()
    )
    hits = use_case.execute(user=_user(), text="doc")
    assert [h.object_id for h in hits] == [str(d.id) for d in sorted(docs, key=lambda d: str(d.id))]
    assert all(h.index_source == INDEX_SOURCE_LEXICAL for h in hits)
    assert all(h.score > 0 for h in hits)


def test_semantic_exception_degrades_to_lexical(db, repo, embedder):
    class BrokenVectorRepository(FakeVectorRepository):
        def search(self, vector, *, limit=50):
            raise RuntimeError("vector store unreachable")

    doc = UniversalObject.create(ObjectType.DOCUMENT, "Resilient Doc", created_by="f:1")
    _seed(db, repo, embedder, doc)
    broken = BrokenVectorRepository()

    hits = _use_case(db, repo, broken, embedder).execute(user=_user(), text="resilient")
    assert [h.object_id for h in hits] == [str(doc.id)]
    assert hits[0].index_source == INDEX_SOURCE_LEXICAL


def test_semantic_textless_query_is_lexical(db, repo, embedder):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Exact Title", created_by="f:1")
    vectors = _seed(db, repo, embedder, doc)
    # Title-only queries have no query vector — the semantic leg is skipped.
    hits = _use_case(db, repo, vectors, embedder).execute(user=_user(), title="exact title")
    assert [h.object_id for h in hits] == [str(doc.id)]
    assert hits[0].index_source == INDEX_SOURCE_LEXICAL


# ------------------------------------------------------------ permissions


def test_permission_gate_applies_after_fusion(db, repo, embedder):
    """The M1 gate is unchanged: an unauthorized object never leaks, even
    when it is the strongest semantic match."""
    open_doc = UniversalObject.create(
        ObjectType.DOCUMENT, "Quantum Entanglement Notes", created_by="f:1"
    )
    secret = UniversalObject.create(
        ObjectType.DOCUMENT, "Quantum Entangled Secrets", created_by="f:2"
    )
    secret.set_metadata(
        MetadataEntry(
            "acl.readers", json.dumps(["obj:user:bob-0002"]),
            MetadataLayer.L1_SYSTEM, Provenance.SYSTEM,
        ),
        actor="system",
    )
    vectors = _seed(db, repo, embedder, open_doc, secret)

    alice = _user("obj:user:alice-0001")
    hits = _use_case(db, repo, vectors, embedder).execute(
        user=alice, text="quantum entangled"
    )
    assert [h.object_id for h in hits] == [str(open_doc.id)]  # never leaked

    bob = _user("obj:user:bob-0002")
    hits_bob = _use_case(db, repo, vectors, embedder).execute(
        user=bob, text="quantum entangled"
    )
    assert {h.object_id for h in hits_bob} == {str(open_doc.id), str(secret.id)}


def test_deleted_row_never_leaks_via_semantic_leg(db, repo, embedder):
    doc = UniversalObject.create(ObjectType.DOCUMENT, "Ghost Doc", created_by="f:1")
    vectors = _seed(db, repo, embedder, doc)
    repo.delete(doc.id)  # delete event NOT drained: lexical row + vector remain
    # The vector leg still returns the ghost, but the authoritative object
    # is gone, so the gate drops it (same M1 protection).
    hits = _use_case(db, repo, vectors, embedder).execute(user=_user(), text="ghost")
    assert hits == []
