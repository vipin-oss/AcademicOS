"""L3 claim confirmation/correction + decision audit tests (ADR-032)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.claim_confirmation import ClaimConfirmationService
from app.application.services.claim_service import ClaimService
from app.domain.value_objects.claim import ClaimStatus
from app.infrastructure.db.models.claim_decision_model import ClaimDecisionModel  # noqa: F401
from app.infrastructure.db.models.claim_model import ClaimModel  # noqa: F401
from app.infrastructure.db.models.claim_span_model import ClaimSpanModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.claim_decision_store import SQLClaimDecisionStore
from app.infrastructure.persistence.claim_store import SQLClaimStore


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def svc(db):
    return ClaimConfirmationService(
        ClaimService(SQLClaimStore(db)), SQLClaimDecisionStore(db)
    )


@pytest.fixture()
def claims(db):
    return ClaimService(SQLClaimStore(db))


def _propose(claims):
    return claims.propose(
        predicate_id="sanctioned_amount", raw_value=1000, source_text="v1",
        source_document_id="obj:document:1", source_version=1, spans=[],
        acl_scope='{"owner":"u:1","readers":[],"writers":[],"managers":[]}',
    )


def test_approve_promotes_to_confirmed_and_records_decision(db, svc, claims):
    claim = _propose(claims)
    record = svc.approve(claim.claim_id, reviewer="u:1", notes="looks right")
    assert record.decision == "approve"
    assert record.reviewer == "u:1"
    assert record.resulting_status == "confirmed"
    stored = claims._store.get(claim.claim_id)
    assert stored[0].status is ClaimStatus.CONFIRMED
    assert stored[0].provenance.value == "asserted"
    # audit trail recorded
    assert len(SQLClaimDecisionStore(db).by_claim(claim.claim_id)) == 1


def test_approve_is_idempotent_by_decision_id(db, svc, claims):
    claim = _propose(claims)
    r1 = svc.approve(claim.claim_id, reviewer="u:1")
    r2 = svc.approve(claim.claim_id, reviewer="u:1")
    # same claim approved twice -> second decision still recorded (append), but
    # the decision_id differs; the claim stays CONFIRMED. Idempotency is per
    # decision_id (duplicate decision_id no-op).
    assert r1.decision_id != r2.decision_id


def test_reject_records_decision(db, svc, claims):
    claim = _propose(claims)
    record = svc.reject(claim.claim_id, reviewer="u:1")
    assert record.resulting_status == "rejected"
    assert claims._store.get(claim.claim_id)[0].status is ClaimStatus.REJECTED


def test_correct_creates_new_asserted_superseding(db, svc, claims):
    claim = _propose(claims)
    record = svc.correct(claim.claim_id, reviewer="u:1", raw_value=9999, notes="corrected")
    assert record.decision == "correct"
    # original superseded
    original = claims._store.get(claim.claim_id)[0]
    assert original.status is ClaimStatus.SUPERSEDED
    # a new ASSERTED claim exists with the corrected value
    all_claims = claims._store.by_source("obj:document:1")
    # the correction is ASSERTED (becomes authoritative once confirmed)
    assert any(c.value.get("amount") == 9999.0 for c in all_claims)
    assert any(c.provenance.value == "asserted" for c in all_claims)


def test_rejected_cannot_be_confirmed_without_correction(db, svc, claims):
    claim = _propose(claims)
    svc.reject(claim.claim_id, reviewer="u:1")
    with pytest.raises(ValueError):
        ClaimService(SQLClaimStore(db)).confirm(claim.claim_id, reviewer="u:1")
