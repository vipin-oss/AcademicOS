"""V3 M5 — typed claims + rung-0 fast path (blueprint §M5, audits A1/A9/A10).

Pins the M5 contract:

- ``claims`` gains typed projections of ``value`` (A1) — writer-populated, not
  a second fact table;
- ``AUTO_SUGGESTED`` is a valid status that is NEVER authoritative (A10) and
  NEVER returned by the rung-0 fast path;
- rung-0 answers from CONFIRMED claims only, invokes no LLM, and reports the
  answering-ladder contract (rung / source_class / evidence page+bbox);
- claims stay bound to ``source_document_id + source_version`` (A9).
"""
from __future__ import annotations

import time

import pytest
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.claim_service import ClaimService
from app.application.use_cases.ai.rung0 import Rung0ClaimAnswerer
from app.domain.value_objects.claim import ClaimStatus
from app.domain.value_objects.span import Span, SpanKind
from app.infrastructure.db.models.cdm_block_model import CdmBlockModel  # noqa: F401
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.claim_store import SQLClaimStore


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _span(page: int | None = None, bbox: tuple | None = None) -> Span:
    return Span(kind=SpanKind.PAGE, source_id="obj:document:1", page=page, bbox=bbox)


def _propose(service, predicate_id, raw_value, source_text, *, spans=None, confidence=0.95):
    return service.propose(
        predicate_id=predicate_id,
        raw_value=raw_value,
        source_text=source_text,
        source_document_id="obj:document:1",
        source_version=1,
        spans=spans or [],
        acl_scope=None,
        fact_confidence=confidence,
    )


def test_money_claim_populates_value_number(db) -> None:
    store = SQLClaimStore(db)
    service = ClaimService(store)
    _propose(service, "sanctioned_amount", "₹50,00,000", "Sanctioned amount.")
    db.commit()

    row = db.execute(
        sqlalchemy.text("SELECT value_number, value_text, value_date FROM claims")
    ).fetchone()
    assert row[0] == 5000000.0  # value_number from amount
    assert row[1] is None
    assert row[2] is None


def test_date_and_text_claims_populate_typed_columns(db) -> None:
    store = SQLClaimStore(db)
    service = ClaimService(store)
    _propose(service, "issue_date", "2024-01-02", "Issued on.")
    _propose(service, "principal_investigator", "Dr. A", "PI is Dr. A.")
    db.commit()

    rows = db.execute(
        sqlalchemy.text(
            "SELECT predicate_id, value_number, value_text, value_date FROM claims "
            "ORDER BY predicate_id"
        )
    ).fetchall()
    by_pred = {r[0]: r for r in rows}
    assert by_pred["issue_date"][3] == "2024-01-02"  # value_date
    assert by_pred["principal_investigator"][2] == "Dr. A"  # value_text
    assert by_pred["issue_date"][1] is None
    assert by_pred["principal_investigator"][1] is None


def test_auto_suggested_is_not_authoritative(db) -> None:
    store = SQLClaimStore(db)
    service = ClaimService(store)
    claim = _propose(service, "sanctioned_amount", "₹1,00,000", "Amount.")
    store.set_status(claim.claim_id, ClaimStatus.AUTO_SUGGESTED)
    db.commit()

    fetched, _spans = store.get(claim.claim_id)
    assert fetched.status is ClaimStatus.AUTO_SUGGESTED
    assert fetched.is_authoritative is False  # A10: only CONFIRMED is canonical


def test_confirmed_by_predicate_excludes_auto_suggested(db) -> None:
    store = SQLClaimStore(db)
    service = ClaimService(store)
    suggested = _propose(service, "sanctioned_amount", "₹1,00,000", "Amount.")
    store.set_status(suggested.claim_id, ClaimStatus.AUTO_SUGGESTED)
    confirmed = _propose(service, "sanctioned_amount", "₹2,00,000", "Amount.")
    service.confirm(confirmed.claim_id)
    db.commit()

    results = store.confirmed_by_predicate("sanctioned_amount")
    assert len(results) == 1
    assert results[0][0].claim_id == confirmed.claim_id


def test_rung0_answers_from_confirmed_claim_with_evidence(db) -> None:
    store = SQLClaimStore(db)
    service = ClaimService(store)
    claim = _propose(
        service,
        "sanctioned_amount",
        "₹50,00,000",
        "Sanctioned amount.",
        spans=[_span(page=3, bbox=(10, 20, 30, 40))],
    )
    service.confirm(claim.claim_id)
    db.commit()

    answerer = Rung0ClaimAnswerer(store)
    answer = answerer.answer("HSRF letter mein sanctioned amount kya hai?", "u:1")
    assert answer is not None
    assert answer.rung == 0
    assert answer.source_class == "claims"
    assert answer.predicate_id == "sanctioned_amount"
    assert "5,000,000.00" in answer.value
    assert answer.evidence and answer.evidence[0].page == 3
    assert answer.evidence[0].bbox == (10, 20, 30, 40)
    # response contract is JSON-safe and carries the ladder fields
    payload = answer.to_dict()
    assert payload["rung"] == 0 and payload["source_class"] == "claims"
    assert payload["evidence"][0]["page"] == 3


def test_rung0_never_returns_auto_suggested(db) -> None:
    store = SQLClaimStore(db)
    service = ClaimService(store)
    suggested = _propose(service, "sanctioned_amount", "₹9,99,999", "Amount.")
    store.set_status(suggested.claim_id, ClaimStatus.AUTO_SUGGESTED)
    db.commit()

    answer = Rung0ClaimAnswerer(store).answer("What is the sanctioned amount?", "u:1")
    assert answer is None  # AUTO_SUGGESTED is never authoritative


def test_rung0_misses_without_matching_predicate(db) -> None:
    store = SQLClaimStore(db)
    service = ClaimService(store)
    claim = _propose(service, "sanctioned_amount", "₹1,00,000", "Amount.")
    service.confirm(claim.claim_id)
    db.commit()

    answer = Rung0ClaimAnswerer(store).answer("Who is the principal investigator?", "u:1")
    # No CONFIRMED principal_investigator claim exists -> fall through.
    assert answer is None


def test_rung0_p95_smoke_budget(db) -> None:
    # Light measurement (not a heavy-load test): rung-0 must stay far under the
    # 100ms blueprint target on an in-memory store; a generous budget avoids
    # shared-hardware flakiness.
    store = SQLClaimStore(db)
    service = ClaimService(store)
    claim = _propose(service, "sanctioned_amount", "₹50,00,000", "Amount.")
    service.confirm(claim.claim_id)
    db.commit()

    answerer = Rung0ClaimAnswerer(store)
    latencies = []
    for _ in range(50):
        t0 = time.perf_counter()
        assert answerer.answer("sanctioned amount?", "u:1") is not None
        latencies.append((time.perf_counter() - t0) * 1000.0)
    p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    assert p95 < 500.0, f"rung-0 p95 {p95:.2f}ms exceeded budget"


def test_claims_bind_to_source_document_and_version(db) -> None:
    # A9: version identity is source_document_id + source_version (revisions
    # upgrade this later). The store must retrieve by that binding.
    store = SQLClaimStore(db)
    service = ClaimService(store)
    _propose(service, "sanctioned_amount", "₹1,00,000", "Amount.")
    db.commit()

    rows = store.for_source_version("obj:document:1", 1)
    assert len(rows) == 1 and rows[0].source_document_id == "obj:document:1"
    assert rows[0].source_version == 1
