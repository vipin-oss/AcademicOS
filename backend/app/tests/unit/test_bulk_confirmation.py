"""V3 M7 bulk confirmation unit tests (ADR-054)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.bulk_confirmation import (
    BULK_CONFIRM_MIN_CONFIDENCE,
    BulkConfirmationService,
)
from app.application.services.claim_service import ClaimService
from app.domain.value_objects.claim import ClaimStatus
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
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _suggest(db, predicate_id="sanctioned_amount", value="1000", confidence=0.99, acl=None):
    service = ClaimService(SQLClaimStore(db))
    claim = service.suggest(
        predicate_id=predicate_id, raw_value=value, source_text=value,
        source_document_id="obj:document:1", source_version=1, spans=[],
        acl_scope=acl, fact_confidence=confidence,
    )
    db.commit()
    return claim


def _svc(db):
    return BulkConfirmationService(SQLClaimStore(db), SQLClaimDecisionStore(db))


def test_confirms_eligible_suggested_claims(db):
    c1 = _suggest(db, value="1000", confidence=0.99)
    c2 = _suggest(db, predicate_id="issue_date", value="2024-01-01", confidence=0.98)
    db.commit()

    result = _svc(db).confirm_suggested(reviewer="u:1")
    db.commit()

    assert result.confirmed == 2 and result.skipped == 0
    assert {d.subject_id for d in result.decisions} == {c1.claim_id, c2.claim_id}
    assert all(d.reviewer == "u:1" for d in result.decisions)
    # both claims now CONFIRMED
    store = SQLClaimStore(db)
    assert store.get(c1.claim_id)[0].status is ClaimStatus.CONFIRMED
    assert store.get(c2.claim_id)[0].status is ClaimStatus.CONFIRMED


def test_below_threshold_is_skipped_not_confirmed(db):
    low = _suggest(db, value="999", confidence=0.80)
    db.commit()

    result = _svc(db).confirm_suggested(reviewer="u:1")
    db.commit()

    assert result.confirmed == 0 and result.skipped == 1
    assert SQLClaimStore(db).get(low.claim_id)[0].status is ClaimStatus.AUTO_SUGGESTED


def test_acl_gated_reviewer_cannot_confirm_out_of_scope(db):
    scope = '{"owner":"u:999","readers":["u:777"],"writers":[],"managers":[]}'
    claim = _suggest(db, value="1000", confidence=0.99, acl=scope)
    db.commit()

    def can_decide(s):
        # reviewer u:1 is neither owner nor reader -> cannot decide
        return False

    result = _svc(db).confirm_suggested(reviewer="u:1", can_decide=can_decide)
    db.commit()

    assert result.confirmed == 0 and result.skipped == 1
    assert SQLClaimStore(db).get(claim.claim_id)[0].status is ClaimStatus.AUTO_SUGGESTED


def test_bulk_confirm_is_attributable_and_undoable(db):
    claim = _suggest(db, value="1000", confidence=0.99)
    db.commit()

    result = _svc(db).confirm_suggested(reviewer="u:42")
    db.commit()
    assert result.decisions[0].reviewer == "u:42"

    # Undoable: the same reviewer can reject via the normal path.
    service = ClaimService(SQLClaimStore(db))
    service.reject(claim.claim_id, reviewer="u:42")
    db.commit()
    assert SQLClaimStore(db).get(claim.claim_id)[0].status is ClaimStatus.REJECTED


def test_min_confidence_default_is_blueprint_threshold():
    assert BULK_CONFIRM_MIN_CONFIDENCE == 0.95
