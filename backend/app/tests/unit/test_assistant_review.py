"""Unit tests for the assistant review queue (Sprint-6 M5).

Enqueue / list pending / approve / reject with idempotent transitions,
oldest-first deterministic ordering, and no duplicate storage — the queue
is a metadata projection over the existing conversation objects.
"""
from __future__ import annotations

from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.dtos.assistant import (
    REVIEW_APPROVED,
    REVIEW_PENDING,
    REVIEW_REJECTED,
)
from app.application.services.assistant_review import (
    AssistantReviewQueue,
    _review_status,
)
from app.application.use_cases.assistant.helpers import (
    append_message,
    create_conversation_object,
    get_conversation_object,
)
from app.domain.entities.object import UniversalObject
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)


def _db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    return session, SQLAlchemyObjectRepository(session)


def _conversation(repo, title="New conversation") -> UniversalObject:
    obj = create_conversation_object(repo, title, "u:1", title_auto=True)
    append_message(obj, "user", "find quantum", None)
    return obj


def _assistant_answer(obj) -> None:
    from app.application.dtos.assistant import AssistantAnswerOutput

    append_message(
        obj,
        "assistant",
        "The grounded answer.",
        AssistantAnswerOutput(
            intent="llm", intent_label="Assistant", question="find quantum",
            summary="The grounded answer.", sources=["llm"],
        ),
    )


def test_enqueue_marks_pending_and_listing_returns_it():
    session, repo = _db()
    try:
        conv = _conversation(repo)
        _assistant_answer(conv)
        repo.save(conv)
        queue = AssistantReviewQueue(repo)

        queue.enqueue(str(conv.id))
        assert _review_status(get_conversation_object(repo, str(conv.id))) == REVIEW_PENDING

        pending = queue.pending()
        assert len(pending) == 1
        assert pending[0].conversation.id == str(conv.id)
        assert pending[0].question == "find quantum"
        assert pending[0].answer == "The grounded answer."
        assert pending[0].message_seq == 2
    finally:
        session.close()


def test_enqueue_is_idempotent_and_skips_no_answer():
    session, repo = _db()
    try:
        empty = create_conversation_object(repo, "Empty", "u:1", title_auto=True)
        queue = AssistantReviewQueue(repo)
        queue.enqueue(str(empty.id))  # no assistant answer -> no-op
        assert _review_status(get_conversation_object(repo, str(empty.id))) == ""

        conv = _conversation(repo)
        _assistant_answer(conv)
        repo.save(conv)
        queue.enqueue(str(conv.id))
        queue.enqueue(str(conv.id))  # idempotent
        assert len(queue.pending()) == 1
    finally:
        session.close()


def test_approve_makes_visible_and_is_idempotent():
    session, repo = _db()
    try:
        conv = _conversation(repo)
        _assistant_answer(conv)
        repo.save(conv)
        queue = AssistantReviewQueue(repo)
        queue.enqueue(str(conv.id))

        queue.approve(str(conv.id))
        assert _review_status(get_conversation_object(repo, str(conv.id))) == REVIEW_APPROVED
        assert queue.pending() == []
        queue.approve(str(conv.id))  # idempotent: no error, state unchanged
        assert _review_status(get_conversation_object(repo, str(conv.id))) == REVIEW_APPROVED
    finally:
        session.close()


def test_reject_hides_and_is_idempotent():
    session, repo = _db()
    try:
        conv = _conversation(repo)
        _assistant_answer(conv)
        repo.save(conv)
        queue = AssistantReviewQueue(repo)
        queue.enqueue(str(conv.id))

        queue.reject(str(conv.id))
        assert _review_status(get_conversation_object(repo, str(conv.id))) == REVIEW_REJECTED
        assert queue.pending() == []
        queue.reject(str(conv.id))  # idempotent
        assert _review_status(get_conversation_object(repo, str(conv.id))) == REVIEW_REJECTED
    finally:
        session.close()


def test_pending_ordering_is_deterministic():
    session, repo = _db()
    try:
        ids = []
        for title in ("B", "A", "C"):
            conv = _conversation(repo, title=title)
            _assistant_answer(conv)
            repo.save(conv)
            ids.append(str(conv.id))
        queue = AssistantReviewQueue(repo)
        for cid in ids:
            queue.enqueue(cid)
        pending = queue.pending()
        assert [p.conversation.id for p in pending] == sorted(ids)  # object_id order
    finally:
        session.close()


def test_duplicate_approval_and_rejection_are_terminal():
    session, repo = _db()
    try:
        conv = _conversation(repo)
        _assistant_answer(conv)
        repo.save(conv)
        queue = AssistantReviewQueue(repo)
        queue.enqueue(str(conv.id))

        queue.approve(str(conv.id))
        queue.reject(str(conv.id))  # after approval -> reject wins (human override)
        assert _review_status(get_conversation_object(repo, str(conv.id))) == REVIEW_REJECTED
        queue.approve(str(conv.id))  # ...and approve again -> terminal flip works
        assert _review_status(get_conversation_object(repo, str(conv.id))) == REVIEW_APPROVED
    finally:
        session.close()
