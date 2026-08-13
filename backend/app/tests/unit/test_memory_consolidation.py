"""Unit tests for memory consolidation & forgetting (Sprint-8 M4).

Covers the pure similarity function, duplicate / near-identical grouping,
the review-aware canonical choice, the supersede mechanics (terminal
status, VERSION_OF edge, nothing deleted — messages/citations/review/
permissions intact), determinism, and the no-op guarantees (clean base,
already-superseded conversations never re-processed).
"""
from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.dtos.assistant import (
    AssistantAnswerOutput,
    AssistantCitation,
    REVIEW_APPROVED,
    REVIEW_PENDING,
)
from app.application.services.assistant_review import AssistantReviewQueue
from app.application.services.memory_consolidation import (
    MemoryConsolidationService,
    answer_similarity,
)
from app.application.use_cases.assistant.helpers import (
    append_message,
    create_conversation_object,
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, Provenance, RelationshipKind
from app.domain.value_objects.metadata import MetadataEntry, MetadataLayer
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
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
def repo(db) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


def _conversation(
    repo,
    *,
    question: str = "find quantum",
    answer: str = "The quantum answer.",
    citations: tuple[AssistantCitation, ...] = (),
    review: str | None = None,
    created_by: str = "u:1",
) -> UniversalObject:
    conv = create_conversation_object(repo, "New conversation", created_by, title_auto=True)
    append_message(conv, "user", question, None)
    append_message(
        conv,
        "assistant",
        answer,
        AssistantAnswerOutput(
            intent="llm", intent_label="Assistant", question=question,
            summary=answer, sources=["llm"], citations=list(citations),
        ),
    )
    if review is not None:
        conv.set_metadata(
            MetadataEntry(
                "assistant.review_status", review,
                MetadataLayer.L1_SYSTEM, Provenance.SYSTEM,
            ),
            actor="system",
        )
    repo.save(conv)
    return conv


def _citation() -> AssistantCitation:
    return AssistantCitation(
        number=1, object_id="obj:document:1", object_type="document",
        title="Quantum Mechanics Notes", sources=("search",), version=1, score=0.9,
    )


def _reload(repo, obj: UniversalObject) -> UniversalObject:
    return repo.get_by_id(obj.id)


# ------------------------------------------------------------ similarity
def test_answer_similarity_is_deterministic_and_bounded():
    assert answer_similarity("The quantum answer.", "The quantum answer.") == pytest.approx(1.0)
    assert answer_similarity("", "") == pytest.approx(1.0)
    assert answer_similarity("quantum physics", "sports results") == 0.0
    assert answer_similarity("The quantum answer.", "The quantum answer is here.") > 0.5
    assert answer_similarity("Quantum", "quantum") == pytest.approx(1.0)  # case-insensitive


# ---------------------------------------------------------- consolidation
def test_exact_duplicates_are_superseded_by_the_newest(repo):
    older = _conversation(repo)
    middle = _conversation(repo)
    newer = _conversation(repo)

    report = MemoryConsolidationService(repo).consolidate(actor="system")

    assert report.scanned == 3
    assert report.consolidated == 2
    pairs = {p.conversation_id: p.canonical_id for p in report.superseded}
    assert pairs[str(older.id)] == str(newer.id)
    assert pairs[str(middle.id)] == str(newer.id)
    # The canonical stays active; the duplicates are terminal SUPERSEDED.
    assert _reload(repo, newer).status is ObjectStatus.ACTIVE
    assert _reload(repo, older).status is ObjectStatus.SUPERSEDED
    assert _reload(repo, middle).status is ObjectStatus.SUPERSEDED
    # The VERSION_OF graph edge records the replacement.
    older_reloaded = _reload(repo, older)
    assert ObjectId(str(newer.id)) in older_reloaded.related_ids(RelationshipKind.VERSION_OF)


def test_near_identical_memories_are_consolidated(repo):
    _conversation(repo, answer="The quantum answer explains superposition.")
    _conversation(repo, answer="The quantum answer explains superposition clearly.")

    report = MemoryConsolidationService(repo).consolidate(actor="system")
    assert report.consolidated == 1


def test_different_questions_are_never_consolidated(repo):
    _conversation(repo, question="find quantum", answer="Quantum answer.")
    _conversation(repo, question="what is a black hole", answer="Gravity answer.")

    report = MemoryConsolidationService(repo).consolidate(actor="system")
    assert report.consolidated == 0
    assert report.superseded == ()


def test_same_question_dissimilar_answers_are_not_merged(repo):
    _conversation(repo, question="find quantum", answer="Quantum mechanics answer.")
    _conversation(repo, question="find quantum", answer="Sports and weather report.")

    report = MemoryConsolidationService(repo).consolidate(actor="system")
    assert report.consolidated == 0


def test_nothing_is_deleted_and_data_is_preserved(repo):
    older = _conversation(repo, citations=(_citation(),), review=REVIEW_APPROVED)
    newer = _conversation(repo)
    MemoryConsolidationService(repo).consolidate(actor="system")

    # The approved older memory is the canonical (stays ACTIVE); the
    # newer duplicate is superseded — nothing is deleted.
    assert _reload(repo, older).status is ObjectStatus.ACTIVE
    superseded = _reload(repo, newer)
    assert superseded.status is ObjectStatus.SUPERSEDED
    # Messages (with the citations) are fully intact.
    from app.application.use_cases.assistant.helpers import read_messages

    messages = read_messages(superseded)
    assert len(messages) == 2
    assert messages[1][1]["role"] == "assistant"
    assert messages[1][1]["answer"]["summary"] == "The quantum answer."
    # The canonical's citations are preserved.
    canonical_messages = read_messages(_reload(repo, older))
    assert canonical_messages[1][1]["answer"]["citations"][0]["title"] == "Quantum Mechanics Notes"
    # Review status preserved on the object; audit history untouched.
    from app.application.services.assistant_review import _review_status

    assert _review_status(_reload(repo, older)) == REVIEW_APPROVED


def test_approved_memory_stays_canonical_over_newer_unreviewed(repo):
    approved = _conversation(repo, review=REVIEW_APPROVED)
    newer_unreviewed = _conversation(repo)

    report = MemoryConsolidationService(repo).consolidate(actor="system")
    pairs = {p.conversation_id: p.canonical_id for p in report.superseded}
    # The approved (older) memory is the canonical — the newer unreviewed
    # duplicate is superseded BY it (never hide approved content).
    assert pairs[str(newer_unreviewed.id)] == str(approved.id)
    assert _reload(repo, approved).status is ObjectStatus.ACTIVE
    assert _reload(repo, newer_unreviewed).status is ObjectStatus.SUPERSEDED


def test_unreviewed_stays_canonical_over_pending(repo):
    pending = _conversation(repo, review=REVIEW_PENDING)
    unreviewed = _conversation(repo)

    report = MemoryConsolidationService(repo).consolidate(actor="system")
    pairs = {p.conversation_id: p.canonical_id for p in report.superseded}
    assert pairs[str(pending.id)] == str(unreviewed.id)
    assert _reload(repo, unreviewed).status is ObjectStatus.ACTIVE


def test_consolidation_is_deterministic_and_idempotent(repo):
    _conversation(repo)
    _conversation(repo)
    service = MemoryConsolidationService(repo)

    first = service.consolidate(actor="system")
    second = service.consolidate(actor="system")
    # The second pass touches nothing: the superseded conversation is no
    # longer ACTIVE, so it is never re-processed (only the canonical is
    # scanned, and it has no remaining duplicates).
    assert first.consolidated == 1
    assert second.consolidated == 0
    assert second.scanned == 1
    assert second.superseded == ()


def test_clean_base_is_a_no_op(repo):
    _conversation(repo)
    report = MemoryConsolidationService(repo).consolidate(actor="system")
    assert report.scanned == 1
    assert report.consolidated == 0


def test_consolidation_after_human_approval(repo):
    older = _conversation(repo)
    newer = _conversation(repo)
    AssistantReviewQueue(repo).enqueue(str(older.id))
    AssistantReviewQueue(repo).approve(str(older.id))

    report = MemoryConsolidationService(repo).consolidate(actor="system")
    pairs = {p.conversation_id: p.canonical_id for p in report.superseded}
    assert pairs[str(newer.id)] == str(older.id)  # approved wins


# ---------------------------------------------------------------------------
# Determinism fix — monotonic audit clock + total-order canonical selection
# ---------------------------------------------------------------------------
def test_audit_created_at_is_strictly_monotonic():
    """Root-cause guard: consecutive audit timestamps never tie.

    Memory consolidation picks the newest ``created_at`` as canonical. If the
    wall clock yields identical instants for back-to-back creations, the
    choice becomes nondeterministic. This asserts the clock is strictly
    increasing, so sequential creations always order correctly.
    """
    from itertools import pairwise

    from app.domain.value_objects import audit as audit_mod

    stamps = [audit_mod._utcnow() for _ in range(1000)]
    assert all(b > a for a, b in pairwise(stamps))


def test_canonical_selection_is_deterministic_on_timestamp_tie(repo):
    """Exact-timestamp tie cannot produce nondeterministic canonical choice.

    Two duplicate conversations are forced to carry the *identical*
    ``created_at`` (the cross-process scenario where even a monotonic
    in-process clock cannot guarantee distinct instants). Canonical selection
    must still be deterministic — resolved by the documented total-order
    tiebreak (created_at, then object ID) — never by ``max``'s iteration order.
    """
    import datetime as dt

    from app.application.use_cases.assistant.helpers import all_conversations
    from app.domain.value_objects.audit import AuditFields

    first = _conversation(repo)
    second = _conversation(repo)

    # Force an identical created_at on both objects.
    tied_at = dt.datetime(2026, 8, 13, 10, 0, 0, tzinfo=dt.UTC)
    for obj in (first, second):
        obj.audit = AuditFields(created_by="u:1", created_at=tied_at)
        repo.save(obj)

    report = MemoryConsolidationService(repo).consolidate(actor="system")
    assert report.consolidated == 1

    active = {
        str(o.id)
        for o in all_conversations(repo)
        if o.status is ObjectStatus.ACTIVE
    }
    superseded = {
        str(o.id)
        for o in all_conversations(repo)
        if o.status is ObjectStatus.SUPERSEDED
    }
    # Exactly one remains canonical; the other is superseded.
    assert active | superseded == {str(first.id), str(second.id)}
    assert len(active) == 1
    assert len(superseded) == 1

    # The winner is the documented deterministic total-order maximum
    # (review quality, created_at, object ID) — reproducible every run.
    expected_canonical = max(
        [first, second],
        key=lambda obj: (
            1,
            obj.audit.created_at if obj.audit else "",
            str(obj.id),
        ),
    )
    assert active == {str(expected_canonical.id)}
