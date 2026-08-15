"""Unit tests for outbox-fed semantic indexing (Sprint-5 M2 Phase 4).

The applier now drives BOTH projections from the same relay drain:
version-aware, delete-aware, replay-safe, and rebuild == replay. A vector
failure must never break the lexical index (it stays authoritative).
"""
from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine, select
from sqlalchemy.orm import sessionmaker

from app.application.services.outbox import to_outbox_row
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.vector import VectorDocument
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.search_document_model import SearchDocumentModel
from app.infrastructure.embedding.hashing_embedder import HashingEmbedder
from app.infrastructure.persistence.mapper import SnapshotMapper
from app.infrastructure.persistence.search_mapping import (
    to_search_document,
    to_search_text,
)
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
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


def _lexical_rows(db) -> list[SearchDocumentModel]:
    return db.execute(
        select(SearchDocumentModel).order_by(SearchDocumentModel.object_id)
    ).scalars().all()


def _expected_vector(obj: UniversalObject, embedder) -> tuple[float, ...]:
    """The vector the applier MUST produce for this object (same mapping)."""
    snap = SnapshotMapper.to_snapshot(obj)
    return tuple(embedder.embed(to_search_text(to_search_document(snap))))


# ------------------------------------------------------------ drain -> vectors


def test_commit_to_vector_via_relay(db, repo):
    obj = UniversalObject.create(
        ObjectType.DOCUMENT, "Semantic Paper", created_by="f:1", status=ObjectStatus.ACTIVE
    )
    _save_with_events(repo, obj)
    embedder = HashingEmbedder()
    vectors = FakeVectorRepository()
    SearchIndexApplier(db, vector_repository=vectors, embedder=embedder).apply_pending()

    assert len(vectors) == 1
    stored = vectors.search(_expected_vector(obj, embedder), limit=1)[0]
    assert stored.object_id == str(obj.id)
    assert stored.version == 1
    assert stored.title == "Semantic Paper"
    assert stored.vector == _expected_vector(obj, embedder)
    # Both projections agree on the same event.
    assert len(_lexical_rows(db)) == 1


def test_update_reindexes_vector_with_new_version(db, repo):
    obj = UniversalObject.create(ObjectType.DOCUMENT, "v1 title", created_by="f:1")
    _save_with_events(repo, obj)
    embedder = HashingEmbedder()
    vectors = FakeVectorRepository()
    applier = SearchIndexApplier(db, vector_repository=vectors, embedder=embedder)
    applier.apply_pending()

    loaded = repo.get(obj.id)
    assert loaded is not None
    loaded.rename("v2 title", actor="f:1")
    _save_with_events(repo, loaded)
    applier.apply_pending()

    assert len(vectors) == 1  # one projection, never a history
    stored = vectors.search(_expected_vector(loaded, embedder), limit=1)[0]
    assert stored.version == 2
    assert stored.title == "v2 title"


def test_delete_removes_vector_via_relay(db, repo):
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Gone", created_by="f:1")
    _save_with_events(repo, obj)
    embedder = HashingEmbedder()
    vectors = FakeVectorRepository()
    applier = SearchIndexApplier(db, vector_repository=vectors, embedder=embedder)
    applier.apply_pending()
    assert len(vectors) == 1

    repo.delete(obj.id)
    applier.apply_pending()
    assert len(vectors) == 0
    assert _lexical_rows(db) == []


def test_replay_is_idempotent_for_vectors(db, repo):
    obj = UniversalObject.create(ObjectType.DOCUMENT, "Stable", created_by="f:1")
    _save_with_events(repo, obj)
    embedder = HashingEmbedder()
    vectors = FakeVectorRepository()
    applier = SearchIndexApplier(db, vector_repository=vectors, embedder=embedder)
    applier.apply_pending()
    before = {d.object_id: d.version for d in vectors.search(_expected_vector(obj, embedder))}

    assert applier.apply_pending() == {"applied": 0}  # nothing left
    after = {d.object_id: d.version for d in vectors.search(_expected_vector(obj, embedder))}
    assert after == before
    assert len(vectors) == 1


def test_out_of_order_application_converges(db, repo):
    """Re-applying a stale event (older version) never regresses the vector."""
    obj = UniversalObject.create(ObjectType.DOCUMENT, "v1 title", created_by="f:1")
    _save_with_events(repo, obj)
    loaded = repo.get(obj.id)
    assert loaded is not None
    loaded.rename("v2 title", actor="f:1")
    _save_with_events(repo, loaded)

    embedder = HashingEmbedder()
    vectors = FakeVectorRepository()
    applier = SearchIndexApplier(db, vector_repository=vectors, embedder=embedder)
    applier.apply_pending()  # drains both events; ends at v2
    assert vectors.search(_expected_vector(loaded, embedder), limit=1)[0].version == 2

    # A stale re-delivery (v1 event content, fresh id) is re-derived from
    # the LATEST durable state -> still v2.
    from app.domain.events import ObjectCreated

    stale = to_outbox_row(ObjectCreated(aggregate_id=obj.id, title="v1 title"))
    db.add(__import__("app.infrastructure.db.models.outbox_model", fromlist=["OutboxEventModel"]).OutboxEventModel(**stale))
    db.commit()
    applier.apply_pending()
    current = repo.get(obj.id)
    assert current is not None
    assert vectors.search(_expected_vector(current, embedder), limit=1)[0].version == 2
    assert len(vectors) == 1


# --------------------------------------------------------------- failure mode


def test_vector_failure_never_breaks_lexical_index(db, repo):
    class BrokenVectors(FakeVectorRepository):
        def upsert(self, document: VectorDocument) -> None:
            raise RuntimeError("vector store unreachable")

        def delete(self, object_id: str) -> None:
            raise RuntimeError("vector store unreachable")

    obj = UniversalObject.create(ObjectType.DOCUMENT, "Resilient", created_by="f:1")
    _save_with_events(repo, obj)

    applier = SearchIndexApplier(
        db, vector_repository=BrokenVectors(), embedder=HashingEmbedder()
    )
    out = applier.apply_pending()  # must complete and mark delivered
    assert out == {"applied": 1}
    rows = _lexical_rows(db)
    assert len(rows) == 1  # lexical fully indexed
    assert rows[0].title == "Resilient"

    # And deletion still clears the lexical projection.
    repo.delete(obj.id)
    assert applier.apply_pending() == {"applied": 1}
    assert _lexical_rows(db) == []


def test_vector_rebuild_failure_leaves_lexical_intact(db, repo):
    class BrokenClear(FakeVectorRepository):
        def clear(self) -> None:
            raise RuntimeError("vector store unreachable")

    obj = UniversalObject.create(ObjectType.DOCUMENT, "Atomic", created_by="f:1")
    _save_with_events(repo, obj)
    applier = SearchIndexApplier(db, vector_repository=BrokenClear(), embedder=HashingEmbedder())
    applier.apply_pending()

    out = applier.rebuild()  # lexical rebuild succeeds; vector rebuild fails silently
    assert out == {"indexed": 1}
    assert len(_lexical_rows(db)) == 1  # lexical authoritative and intact


# ------------------------------------------------------------------- rebuild


def test_rebuild_matches_replay_for_vectors(db, repo):
    obj = UniversalObject.create(ObjectType.COURSE, "Physics 101", created_by="f:1")
    _save_with_events(repo, obj)
    loaded = repo.get(obj.id)
    assert loaded is not None
    loaded.rename("Physics 201", actor="f:1")
    _save_with_events(repo, loaded)
    obj2 = UniversalObject.create(ObjectType.DOCUMENT, "Notes", created_by="f:1")
    _save_with_events(repo, obj2)

    embedder = HashingEmbedder()
    vectors = FakeVectorRepository()
    applier = SearchIndexApplier(db, vector_repository=vectors, embedder=embedder)
    applier.apply_pending()
    drained = {
        (d.object_id, d.title, d.version, d.vector)
        for d in vectors.search([0.0] * embedder.dimensions, limit=50)
    }

    vectors.clear()
    applier.rebuild()
    rebuilt = {
        (d.object_id, d.title, d.version, d.vector)
        for d in vectors.search([0.0] * embedder.dimensions, limit=50)
    }

    assert rebuilt == drained
    assert {d.title for d in vectors.search([0.0] * embedder.dimensions, limit=50)} == {
        "Physics 201",
        "Notes",
    }


def test_rebuild_without_vector_wiring_is_m1_behavior(db, repo):
    obj = UniversalObject.create(ObjectType.DOCUMENT, "M1 Only", created_by="f:1")
    _save_with_events(repo, obj)
    applier = SearchIndexApplier(db)  # no vector repo, no embedder
    assert applier.apply_pending() == {"applied": 1}
    assert applier.rebuild() == {"indexed": 1}
    assert len(_lexical_rows(db)) == 1
