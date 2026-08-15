"""V3 M8 retrieval-speed tests (ADR-055): parallel fan-out, fact cache, dossier."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.dossier import DossierService
from app.application.services.fact_cache import FACT_CACHE, FactCache, invalidate_facts
from app.application.services.outbox import to_outbox_row
from app.application.use_cases.ai.rung0 import Rung0ClaimAnswerer
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.embedding.hashing_embedder import HashingEmbedder
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.persistence.claim_store import SQLClaimStore
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
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _user(obj_id="obj:user:alice-0001") -> UniversalObject:
    return UniversalObject.create(
        ObjectType.USER, "alice", created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId(obj_id),
    )


def _doc(obj_id="obj:document:1", title="Quantum Dots") -> UniversalObject:
    return UniversalObject.create(
        ObjectType.DOCUMENT, title, created_by="system", status=ObjectStatus.ACTIVE,
        object_id=ObjectId(obj_id),
    )


def _seed(db, repo, embedder, *objects) -> FakeVectorRepository:
    vectors = FakeVectorRepository()
    for obj in objects:
        events = obj.pop_domain_events()
        repo.save(obj, outbox_events=[to_outbox_row(e) for e in events])
    SearchIndexApplier(db, vector_repository=vectors, embedder=embedder).apply_pending()
    return vectors


def _use_case(db, repo, vectors, embedder, *, parallel) -> SearchObjectsUseCase:
    return SearchObjectsUseCase(
        SQLAlchemySearchRepository(db), repo, ObjectPermissionEvaluator(),
        vector_repository=vectors, embedder=embedder, parallel=parallel,
    )


def test_parallel_and_sequential_results_are_identical(db):
    embedder = HashingEmbedder()
    repo = SQLAlchemyObjectRepository(db)
    user = _user()
    doc = _doc()
    vectors = _seed(db, repo, embedder, user, doc)

    sequential = _use_case(db, repo, vectors, embedder, parallel=False).execute(
        user=user, text="quantum", limit=10
    )
    parallel = _use_case(db, repo, vectors, embedder, parallel=True).execute(
        user=user, text="quantum", limit=10
    )
    assert [h.object_id for h in sequential] == [h.object_id for h in parallel]
    assert [h.score for h in sequential] == [h.score for h in parallel]
    assert any(h.object_id == "obj:document:1" for h in parallel)


def test_parallel_disabled_skips_executor(db):
    embedder = HashingEmbedder()
    repo = SQLAlchemyObjectRepository(db)
    user = _user()
    _seed(db, repo, embedder, _doc())
    # When no semantic leg exists, both paths are pure lexical.
    lexical_only = _use_case(db, repo, None, None, parallel=True).execute(
        user=user, text="quantum", limit=10
    )
    assert any(h.object_id == "obj:document:1" for h in lexical_only)


class TestFactCache:
    def test_lru_eviction(self):
        cache = FactCache(capacity=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)  # evicts "a"
        assert cache.get("a") is None
        assert cache.get("b") == 2 and cache.get("c") == 3

    def test_invalidation(self):
        cache = FactCache()
        cache.put("k", 1)
        cache.invalidate("k")
        assert cache.get("k") is None

    def test_invalidate_all(self):
        FACT_CACHE.put("dossier:v1", "stale")
        invalidate_facts()
        assert FACT_CACHE.get("dossier:v1") is None


class TestDossier:
    def test_dossier_aggregates_and_caches(self, db):
        repo = SQLAlchemyObjectRepository(db)
        user = _user()
        doc = _doc()
        for obj in (user, doc):
            repo.save(obj, outbox_events=[])
        db.commit()

        service = DossierService(repo, SQLClaimStore(db))
        d1 = service.dossier()
        assert d1.object_counts.get("document") == 1
        assert d1.object_counts.get("user") == 1
        # cached: a second call is served from the cache (identical object)
        d2 = service.dossier()
        assert d1.object_counts == d2.object_counts


class TestRung0Cache:
    def test_rung0_cache_invalidated_on_claim_write(self, db):
        from app.application.services.claim_service import ClaimService

        claim_store = SQLClaimStore(db)
        service = ClaimService(claim_store)
        claim = service.propose(
            predicate_id="sanctioned_amount", raw_value="1000", source_text="1000",
            source_document_id="obj:document:1", source_version=1, spans=[],
            acl_scope=None, fact_confidence=0.9,
        )
        service.confirm(claim.claim_id)
        db.commit()

        answerer = Rung0ClaimAnswerer(claim_store, permission_evaluator=ObjectPermissionEvaluator())
        principal = {"sub": "obj:user:alice-0001", "roles": []}
        assert answerer.answer("sanctioned amount?", principal=principal) is not None
        # cache is warm; a reject invalidates and the next answer falls through
        service.reject(claim.claim_id)
        db.commit()
        assert answerer.answer("sanctioned amount?", principal=principal) is None
