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

from app.application.dtos.assistant import (
    REVIEW_APPROVED,
    REVIEW_PENDING,
    REVIEW_REJECTED,
)
from app.application.services.assistant_review import (
    REVIEW_NOTES_MAX,
    ReviewDecision,
    _review_status,
)
# Register every table before ``Base.metadata.create_all`` (the repository
# writes object_relationships / object_versions / outbox_events too).
from app.infrastructure.db.models.object_model import Base  # noqa: E402
from app.infrastructure.db.models.object_relationship_model import (  # noqa: E402,F401
    ObjectRelationshipModel,
)
from app.infrastructure.db.models.object_version_model import ObjectVersionModel  # noqa: E402,F401
from app.infrastructure.db.models.outbox_model import OutboxEventModel  # noqa: E402,F401
from app.infrastructure.db.models.search_document_model import SearchDocumentModel  # noqa: E402,F401
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


# ------------------------------------------------------------- the queue
def _queue_world(db):
    """A conversation with an assistant answer, pending review, plus the
    queue wired with a real decision store."""
    from app.application.dtos.assistant import AssistantAnswerOutput
    from app.application.services.assistant_review import AssistantReviewQueue
    from app.application.use_cases.assistant.helpers import (
        append_message,
        create_conversation_object,
    )
    from app.infrastructure.repositories.sqlalchemy_object_repository import (
        SQLAlchemyObjectRepository,
    )

    repo = SQLAlchemyObjectRepository(db)
    conv = create_conversation_object(repo, "New conversation", "u:1", title_auto=True)
    append_message(conv, "user", "find quantum", None)
    append_message(
        conv,
        "assistant",
        "The grounded answer.",
        AssistantAnswerOutput(
            intent="llm", intent_label="Assistant", question="find quantum",
            summary="The grounded answer.", sources=["llm"],
        ),
    )
    repo.save(conv)
    queue = AssistantReviewQueue(
        repo, decision_store=SQLReviewDecisionStore(db)
    )
    queue.enqueue(str(conv.id))
    return repo, queue, str(conv.id)


def test_approve_records_the_full_human_feedback(db):
    repo, queue, conv_id = _queue_world(db)
    outcome = queue.approve(
        conv_id,
        reviewer="obj:user:reviewer-0001",
        notes="Well grounded, minor wording.",
        rating=4,
        confidence=0.85,
        eval_run_id="run-abc",
    )
    assert outcome.decision is not None
    assert outcome.decision.decision == REVIEW_APPROVED
    assert outcome.decision.reviewer == "obj:user:reviewer-0001"
    assert outcome.decision.notes == "Well grounded, minor wording."
    assert outcome.decision.rating == 4
    assert outcome.decision.confidence == 0.85
    assert outcome.decision.eval_run_id == "run-abc"
    assert outcome.decision.previous_status == REVIEW_PENDING
    assert outcome.decision.created_at

    trail = queue.decisions(conv_id)
    assert len(trail) == 1
    assert trail[0] == outcome.decision


def test_review_history_records_every_action_including_reviews(db):
    repo, queue, conv_id = _queue_world(db)
    queue.approve(conv_id, reviewer="obj:user:r1", notes="Looks good.")
    queue.reject(conv_id, reviewer="obj:user:r2", notes="Factual error.",
                 rating=2, confidence=0.4)
    queue.approve(conv_id, reviewer="obj:user:r3", notes="Fixed.")  # re-review

    trail = queue.decisions(conv_id)
    assert [d.decision for d in trail] == [
        REVIEW_APPROVED, REVIEW_REJECTED, REVIEW_APPROVED,
    ]
    assert [d.previous_status for d in trail] == [
        REVIEW_PENDING, REVIEW_APPROVED, REVIEW_REJECTED,
    ]
    assert [d.reviewer for d in trail] == ["obj:user:r1", "obj:user:r2", "obj:user:r3"]
    # The live state reflects the last action.
    from app.application.services.assistant_review import _review_status
    from app.application.use_cases.assistant.helpers import get_conversation_object

    assert _review_status(get_conversation_object(repo, conv_id)) == REVIEW_APPROVED
    assert queue.pending() == []


def test_recent_decisions_is_the_workspace_feed(db):
    repo, queue, conv_id = _queue_world(db)
    queue.approve(conv_id, reviewer="obj:user:r1")
    # A second conversation in the feed.
    from app.application.dtos.assistant import AssistantAnswerOutput
    from app.application.services.assistant_review import AssistantReviewQueue
    from app.application.use_cases.assistant.helpers import (
        append_message,
        create_conversation_object,
    )
    from app.infrastructure.repositories.sqlalchemy_object_repository import (
        SQLAlchemyObjectRepository,
    )

    repo2 = SQLAlchemyObjectRepository(db)
    conv2 = create_conversation_object(repo2, "Second", "u:1", title_auto=True)
    append_message(conv2, "user", "q", None)
    append_message(
        conv2, "assistant", "Another answer.",
        AssistantAnswerOutput(
            intent="llm", intent_label="Assistant", question="q",
            summary="Another answer.", sources=["llm"],
        ),
    )
    repo2.save(conv2)
    queue2 = AssistantReviewQueue(repo2, decision_store=SQLReviewDecisionStore(db))
    queue2.enqueue(str(conv2.id))
    queue2.reject(str(conv2.id), reviewer="obj:user:r2", rating=1)

    feed = queue.recent_decisions(10)
    assert [d.decision for d in feed] == [REVIEW_REJECTED, REVIEW_APPROVED]
    assert feed[0].conversation_id == str(conv2.id)
    assert [d.decision_id for d in queue.recent_decisions(1)] == [feed[0].decision_id]


def test_queue_without_decision_store_is_backward_compatible(db):
    from app.application.dtos.assistant import AssistantAnswerOutput
    from app.application.services.assistant_review import AssistantReviewQueue
    from app.application.use_cases.assistant.helpers import (
        append_message,
        create_conversation_object,
        get_conversation_object,
    )
    from app.infrastructure.repositories.sqlalchemy_object_repository import (
        SQLAlchemyObjectRepository,
    )

    repo = SQLAlchemyObjectRepository(db)
    conv = create_conversation_object(repo, "New conversation", "u:1", title_auto=True)
    append_message(conv, "user", "q", None)
    append_message(
        conv, "assistant", "Answer.",
        AssistantAnswerOutput(
            intent="llm", intent_label="Assistant", question="q",
            summary="Answer.", sources=["llm"],
        ),
    )
    repo.save(conv)
    queue = AssistantReviewQueue(repo)  # no store -> pre-M5 behavior
    queue.enqueue(str(conv.id))

    outcome = queue.approve(str(conv.id))
    assert outcome.decision is None  # no audit row without a store
    assert outcome.conversation.id == str(conv.id)
    assert _review_status(get_conversation_object(repo, str(conv.id))) == REVIEW_APPROVED
    assert queue.decisions(str(conv.id)) == []
    assert queue.recent_decisions(10) == []


def test_no_decision_recorded_when_nothing_to_review(db):
    from app.application.services.assistant_review import AssistantReviewQueue
    from app.application.use_cases.assistant.helpers import create_conversation_object
    from app.infrastructure.repositories.sqlalchemy_object_repository import (
        SQLAlchemyObjectRepository,
    )

    repo = SQLAlchemyObjectRepository(db)
    conv = create_conversation_object(repo, "Empty", "u:1", title_auto=True)
    repo.save(conv)
    queue = AssistantReviewQueue(
        repo, decision_store=SQLReviewDecisionStore(db)
    )
    outcome = queue.approve(str(conv.id))
    assert outcome.decision is None  # nothing to review -> no audit noise
    assert queue.decisions(str(conv.id)) == []
