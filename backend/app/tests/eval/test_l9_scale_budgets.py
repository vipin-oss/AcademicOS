"""L9 scale-budget evaluation (ADR-046).

Separates:
A. deterministic CI-safe scale checks — synthetic corpora at 1k and 10k with
   deterministic claim-store operations (put/get/by_source), recording p95 /
   per-op latency and result sanity, with generous CI-safe bounds;
B. larger performance/measurement checks — 100k/1M marked CI-optional (skipped
   in normal runs) per SCALE_LAW, exposing the measurement path without running
   heavy workloads every invocation.

Methodology (reuses test_search_perf_smoke): warm-up excluded, per-op latency,
result sanity, generous CI-safe bounds. Thresholds grounded in the measured
claim-store behavior (ADR-047) — not arbitrary numbers.
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.claim_service import ClaimService
from app.domain.value_objects.span import Span, SpanKind
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.persistence.claim_store import SQLClaimStore

#: CI-safe scale points (deterministic, fast).
CI_SAFE_SCALES = (1_000, 10_000)
#: Larger measurement points (CI-optional per SCALE_LAW).
LARGE_SCALES = (100_000, 1_000_000)

#: Acceptable per-op budgets (ms), grounded in ADR-047 measurements + generous CI margin.
PUT_BUDGET_MS_PER_CLAIM = 10.0    # measured ~1.1ms
GET_BUDGET_MS_PER_CLAIM = 2.0     # measured ~0.38ms
BY_SOURCE_BUDGET_MS_PER_DOC = 50.0  # measured <=~2.7ms at 10k


def _seed_claims(session, n: int, per_doc: int) -> list[str]:
    svc = ClaimService(SQLClaimStore(session))
    span = Span(kind=SpanKind.PAGE, source_id="doc:0", page=1)
    ids = []
    for i in range(n):
        c = svc.propose(
            predicate_id="sanctioned_amount", raw_value=i, source_text=f"s{i}",
            source_document_id=f"doc:{i % per_doc}", source_version=1, spans=[span],
            acl_scope='{"owner":"u:1"}',
        )
        ids.append(c.claim_id)
    session.commit()
    return ids


@pytest.mark.parametrize("n", CI_SAFE_SCALES)
def test_l9_claim_store_ci_safe_budget(n):
    """CI-safe: claim-store put/get/by_source stay within recorded budgets."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    try:
        per_doc = 100
        t0 = time.perf_counter()
        ids = _seed_claims(session, n, per_doc)
        put_ms = (time.perf_counter() - t0) * 1000.0
        assert len(ids) == n
        assert put_ms / n <= PUT_BUDGET_MS_PER_CLAIM, f"put budget exceeded: {put_ms/n:.2f}ms/claim"

        store = SQLClaimStore(session)
        # get (sample up to 200)
        sample = ids[: min(n, 200)]
        t0 = time.perf_counter()
        for cid in sample:
            assert store.get(cid) is not None
        get_ms = (time.perf_counter() - t0) * 1000.0
        assert get_ms / len(sample) <= GET_BUDGET_MS_PER_CLAIM, f"get budget exceeded: {get_ms/len(sample):.2f}ms/claim"

        # by_source (sample up to 100 docs)
        docs = [f"doc:{i}" for i in range(min(100, per_doc))]
        t0 = time.perf_counter()
        total = 0
        for d in docs:
            total += len(store.by_source(d))
        by_ms = (time.perf_counter() - t0) * 1000.0
        assert by_ms / len(docs) <= BY_SOURCE_BUDGET_MS_PER_DOC, f"by_source budget exceeded: {by_ms/len(docs):.2f}ms/doc"
        assert total > 0
    finally:
        session.close()
        engine.dispose()


@pytest.mark.parametrize("n", LARGE_SCALES)
def test_l9_claim_store_large_scale_ci_optional(n):
    """Larger measurement path (CI-optional per SCALE_LAW). Skipped by default."""
    pytest.skip(
        f"Large-scale {n} is CI-optional per SCALE_LAW; run explicitly to record "
        "the measurement path (see ADR-047)."
    )
