"""L3 claim/cdm decision store idempotency + audit tests (ADR-032)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.decision_records import DecisionRecord
from app.infrastructure.db.models.cdm_decision_model import CdmDecisionModel  # noqa: F401
from app.infrastructure.db.models.claim_decision_model import ClaimDecisionModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.cdm_decision_store import SQLCdmDecisionStore
from app.infrastructure.persistence.claim_decision_store import SQLClaimDecisionStore


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


def _rec(decision_id="decision:1", subject="claim:1", decision="approve"):
    return DecisionRecord(
        decision_id=decision_id, subject_id=subject, decision=decision,
        reviewer="u:1", previous_status="proposed",
        resulting_status="confirmed", notes="", acl_scope='{"owner":"u:1"}',
    )


def test_claim_decision_idempotent_by_decision_id(db):
    store = SQLClaimDecisionStore(db)
    store.add(_rec())
    store.add(_rec())  # duplicate decision_id -> no-op
    db.flush()
    assert len(store.by_claim("claim:1")) == 1


def test_claim_decision_audit_trail(db):
    store = SQLClaimDecisionStore(db)
    store.add(_rec("decision:1", "claim:1", "reject"))
    store.add(_rec("decision:2", "claim:1", "approve"))
    db.flush()
    trail = store.by_claim("claim:1")
    assert len(trail) == 2
    assert [t.decision for t in trail] == ["reject", "approve"]


def test_cdm_decision_store(db):
    store = SQLCdmDecisionStore(db)
    store.add(DecisionRecord(
        decision_id="cdm:1", subject_id="block:1", decision="approve",
        reviewer="u:1", previous_status="proposed", resulting_status="confirmed",
        notes="", acl_scope='{"owner":"u:1"}',
    ))
    store.add(DecisionRecord(
        decision_id="cdm:1", subject_id="block:1", decision="approve",
        reviewer="u:1", previous_status="proposed", resulting_status="confirmed",
        notes="", acl_scope='{"owner":"u:1"}',
    ))
    db.flush()
    assert len(store.by_block("block:1")) == 1
