"""V3 M7 extraction health + conflict unit tests (ADR-054)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.claim_confirmation import ClaimConfirmationService
from app.application.services.claim_service import ClaimService
from app.application.services.extraction_health import (
    ConflictReport,
    ExtractionHealthService,
)
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


def _propose(db, predicate_id, value, source="obj:document:1"):
    claim = ClaimService(SQLClaimStore(db)).propose(
        predicate_id=predicate_id, raw_value=value, source_text=value,
        source_document_id=source, source_version=1, spans=[], acl_scope=None,
    )
    db.commit()
    return claim


def test_corrections_aggregate_per_predicate(db):
    confirmation = ClaimConfirmationService(
        ClaimService(SQLClaimStore(db)), SQLClaimDecisionStore(db)
    )
    # two sanctioned_amount corrections, one principal_investigator correction
    for _ in range(2):
        c = _propose(db, "sanctioned_amount", "1000")
        confirmation.correct(c.claim_id, reviewer="u:1", raw_value="2000")
    c2 = _propose(db, "principal_investigator", "Dr. X")
    confirmation.correct(c2.claim_id, reviewer="u:2", raw_value="Dr. Y")
    db.commit()

    health = ExtractionHealthService(SQLClaimStore(db), SQLClaimDecisionStore(db)).health()
    assert health.total_corrections == 3
    assert health.by_predicate["sanctioned_amount"] == 2
    assert health.by_predicate["principal_investigator"] == 1


def test_conflict_escalates_when_candidate_differs_from_confirmed(db):
    store = SQLClaimStore(db)
    service = ClaimService(store)
    # confirmed value
    confirmed = _propose(db, "sanctioned_amount", "1000")
    service.confirm(confirmed.claim_id, assert_human=True)
    # a new candidate with a DIFFERENT value
    _propose(db, "sanctioned_amount", "5000")
    db.commit()

    conflicts = ConflictReport(store).conflicts()
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.predicate_id == "sanctioned_amount"
    assert conflict.confirmed_value == 1000.0
    assert conflict.candidate_value == 5000.0


def test_no_conflict_when_values_match(db):
    store = SQLClaimStore(db)
    service = ClaimService(store)
    confirmed = _propose(db, "sanctioned_amount", "1000")
    service.confirm(confirmed.claim_id, assert_human=True)
    _propose(db, "sanctioned_amount", "1000")  # same value -> no conflict
    db.commit()

    assert ConflictReport(store).conflicts() == ()


def test_no_conflict_without_confirmed_fact(db):
    store = SQLClaimStore(db)
    _propose(db, "sanctioned_amount", "1000")
    _propose(db, "sanctioned_amount", "5000")
    db.commit()
    # no CONFIRMED claim -> nothing to contradict
    assert ConflictReport(store).conflicts() == ()
