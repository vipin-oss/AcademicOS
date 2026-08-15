"""Performance smoke for Global Search (Sprint-5 M2 Phase 7).

Methodology
-----------
- Index: 5,000 search documents bulk-seeded into the real
  ``search_documents`` table + 5,000 vectors into the reference
  (in-memory) vector repository — the same structures the relay produces.
- Workload: 25 lexical queries (``text`` LIKE over title/metadata) and 25
  hybrid queries (lexical + embedding + cosine over the vector store),
  warm-up excluded.
- Metric: p95 latency per leg, plus result-set sanity.

Bounds are deliberately generous (CI-safe on shared runners); the measured
numbers are printed and recorded in ``docs/search_collection_policy.md``.
SRS §10.7 targets are R3 steady-state (50B artefacts, 10k tenants) and
cannot be reproduced in CI — the smoke documents the per-query cost at
5,000 documents and the extrapolation gap is stated in the policy doc.
"""
from __future__ import annotations

import statistics
import time

from sqlalchemy import StaticPool, create_engine, insert
from sqlalchemy.orm import sessionmaker

from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.vector import VectorDocument
from app.infrastructure.db.models.object_model import Base, ObjectModel
from app.infrastructure.db.models.search_document_model import SearchDocumentModel
from app.infrastructure.embedding.hashing_embedder import HashingEmbedder
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.repositories.sqlalchemy_search_repository import (
    SQLAlchemySearchRepository,
)
from app.infrastructure.vector_db.fake import FakeVectorRepository

_DOC_COUNT = 5_000
_QUERY_COUNT = 25
_P95_BOUND_SECONDS = 0.5  # generous CI-safe ceiling


def _p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return ordered[index]


def _seed(engine) -> tuple[SQLAlchemySearchRepository, FakeVectorRepository, HashingEmbedder]:
    """Bulk-seed both projections with 5,000 deterministic documents."""
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    embedder = HashingEmbedder()
    rows = [
        {
            "object_id": f"obj:document:{i:05d}",
            "object_type": "document",
            "title": f"Perf Document {i}",
            "metadata_text": "searchable content summary",
            "version": 1,
        }
        for i in range(_DOC_COUNT)
    ]
    db.execute(insert(SearchDocumentModel), rows)
    # The authoritative objects behind the projections (the R4 gate loads
    # them): bulk-inserted rows with the snapshot JSON shapes.
    db.execute(
        insert(ObjectModel),
        [
            {
                "id": f"obj:document:{i:05d}",
                "object_type": "document",
                "title": f"Perf Document {i}",
                "status": "active",
                "version": 1,
                "metadata_json": [],
                "audit_json": {
                    "created_by": "perf",
                    "created_at": "2026-01-01T00:00:00+00:00",
                },
            }
            for i in range(_DOC_COUNT)
        ],
    )
    db.commit()

    vectors = FakeVectorRepository()
    for i in range(_DOC_COUNT):
        text = f"Perf Document {i}\nsearchable content summary"
        vectors.upsert(
            VectorDocument(
                object_id=f"obj:document:{i:05d}",
                object_type="document",
                title=f"Perf Document {i}",
                metadata_text="searchable content summary",
                version=1,
                vector=tuple(embedder.embed(text)),
            )
        )
    return SQLAlchemySearchRepository(db), vectors, embedder


def test_search_perf_smoke_lexical_and_hybrid():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        index, vectors, embedder = _seed(engine)

        # Warm-up (excludes one-time costs: first LIKE scan, first embed).
        index.search(text="searchable content", limit=50)

        lexical_samples: list[float] = []
        for _ in range(_QUERY_COUNT):
            start = time.perf_counter()
            index.search(text="searchable content", limit=50)
            lexical_samples.append(time.perf_counter() - start)

        db = sessionmaker(bind=engine, expire_on_commit=False)()
        use_case = SearchObjectsUseCase(
            SQLAlchemySearchRepository(db),
            SQLAlchemyObjectRepository(db),
            ObjectPermissionEvaluator(),
            vector_repository=vectors,
            embedder=embedder,
        )
        hybrid_samples: list[float] = []
        hit_counts: list[int] = []
        for _ in range(_QUERY_COUNT):
            start = time.perf_counter()
            hits = use_case.execute(
                user=UniversalObject.create(
                    ObjectType.USER,
                    "perf",
                    created_by="system",
                    status=ObjectStatus.ACTIVE,
                    object_id=ObjectId("obj:user:perf-0001"),
                ),
                text="searchable content",
                limit=50,
            )
            hybrid_samples.append(time.perf_counter() - start)
            hit_counts.append(len(hits))

        lexical_p95 = _p95(lexical_samples)
        hybrid_p95 = _p95(hybrid_samples)

        print(
            f"\n[perf-smoke] documents={_DOC_COUNT} queries={_QUERY_COUNT} "
            f"lexical_p95={lexical_p95 * 1000:.1f}ms "
            f"hybrid_p95={hybrid_p95 * 1000:.1f}ms "
            f"hits={statistics.median(hit_counts)}"
        )

        # Honest bounds: the smoke exists to catch order-of-magnitude
        # regressions, not to benchmark micro-variation.
        assert lexical_p95 < _P95_BOUND_SECONDS
        assert hybrid_p95 < _P95_BOUND_SECONDS
        assert statistics.median(hit_counts) > 0
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
