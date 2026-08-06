"""Unit tests for review-decision persistence (Sprint-7 M5).

The audit-record value (ReviewDecision invariants: identity fields,
decision domain, notes cap, rating 1-5, confidence 0-1, blank eval_run_id
rejection, timestamp) and the store round-trips: append-only rows,
per-conversation chronological audit trails, and the newest-first
workspace feed.
"""
from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.dtos.assistant import REVIEW_APPROVED, REVIEW_REJECTED
from app.application.services.assistant_review import (
    REVIEW_NOTES_MAX,
    ReviewDecision,
)
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.review_decision_store import (
    SQLReviewDecisionStore,
)


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
def store(db) -> SQLReviewDecisionStore:
    return SQLReviewDecisionStore(db)


def _decision(
    *,
    decision_id: str = "d-1",
    conversation_id: str = "obj:ai_conversation:1",
    decision: str = REVIEW_APPROVED,
    reviewer: str = "obj:user:reviewer-0001",
    previous_status: str = "pending",
    notes: str = "Grounded and well cited.",
    rating: int | None = 5,
    confidence: float | None = 0.9,
    eval_run_id: str | None = "run-1",
    created_at: str = "2026-08-06T10:00:00+00:00",
) -> ReviewDecision:
    return ReviewDecision(
        decision_id=decision_id,
        conversation_id=conversation_id,
        decision=decision,
        reviewer=reviewer,
        previous_status=previous_status,
        notes=notes,
        rating=rating,
        confidence=confidence,
        eval_run_id=eval_run_id,
        created_at=created_at,
    )


# -------------------------------------------------------------- record
def test_decision_round_trips_through_the_store(db, store):
    store.add(_decision())
    fetched = store.by_conversation("obj:ai_conversation:1")
    assert fetched == [_decision()]
    assert fetched[0].rating == 5
    assert fetched[0].confidence == 0.9
    assert fetched[0].eval_run_id == "run-1"


def test_decision_invariants_are_enforced():
    with pytest.raises(ValueError, match="identity"):
        _decision(reviewer="")
    with pytest.raises(ValueError, match="Unknown review decision"):
        _decision(decision="maybe")
    with pytest.raises(ValueError, match="at most"):
        _decision(notes="x" * (REVIEW_NOTES_MAX + 1))
    with pytest.raises(ValueError, match="rating"):
        _decision(rating=0)
    with pytest.raises(ValueError, match="rating"):
        _decision(rating=6)
    with pytest.raises(ValueError, match="confidence"):
        _decision(confidence=-0.1)
    with pytest.raises(ValueError, match="confidence"):
        _decision(confidence=1.1)
    with pytest.raises(ValueError, match="eval_run_id"):
        _decision(eval_run_id="  ")
    with pytest.raises(ValueError, match="created_at"):
        _decision(created_at="")


def test_decision_optional_feedback_fields_may_be_absent():
    decision = _decision(rating=None, confidence=None, eval_run_id=None)
    assert decision.rating is None
    assert decision.confidence is None
    assert decision.eval_run_id is None


# --------------------------------------------------------------- store
def test_by_conversation_returns_the_chronological_audit_trail(db, store):
    store.add(_decision(decision_id="d1", created_at="2026-08-06T09:00:00+00:00"))
    store.add(_decision(decision_id="d2", created_at="2026-08-06T11:00:00+00:00"))
    store.add(_decision(decision_id="d3", created_at="2026-08-06T10:00:00+00:00"))
    assert [d.decision_id for d in store.by_conversation("obj:ai_conversation:1")] == [
        "d1", "d3", "d2",
    ]
    # Other conversations are never mixed in.
    store.add(
        _decision(
            decision_id="other",
            conversation_id="obj:ai_conversation:9",
            decision=REVIEW_REJECTED,
        )
    )
    assert [d.decision_id for d in store.by_conversation("obj:ai_conversation:1")] == [
        "d1", "d3", "d2",
    ]
    assert store.by_conversation("obj:ai_conversation:missing") == []


def test_recent_returns_the_newest_first_workspace_feed(db, store):
    store.add(_decision(decision_id="d1", created_at="2026-08-06T09:00:00+00:00"))
    store.add(_decision(decision_id="d2", created_at="2026-08-06T11:00:00+00:00"))
    store.add(_decision(decision_id="d3", created_at="2026-08-06T10:00:00+00:00"))
    assert [d.decision_id for d in store.recent(10)] == ["d2", "d3", "d1"]
    assert [d.decision_id for d in store.recent(2)] == ["d2", "d3"]
    assert store.recent(0) == []
