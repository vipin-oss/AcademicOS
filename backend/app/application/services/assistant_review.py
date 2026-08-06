"""Assistant review queue (Sprint-6 M5).

One queue implementation — the review state lives on the conversation
object (``assistant.review_status`` metadata: pending / approved /
rejected), so there is no separate table and no duplicate persistence.
The queue is a projection over the existing repository:

- ``enqueue``      — mark a conversation's latest assistant answer pending;
- ``pending``      — every conversation awaiting review (oldest first);
- ``approve``      — approved: the answer becomes visible;
- ``reject``       — rejected: the answer stays hidden.

Approve/reject are idempotent state transitions: approving an approved
conversation is a no-op (no error), rejecting a rejected one likewise.
Concurrent double-actions collapse onto the same terminal state via the
repository's existing optimistic concurrency (version guard).
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field

from app.application.dtos.assistant import (
    KEY_REVIEW_STATUS,
    REVIEW_APPROVED,
    REVIEW_PENDING,
    REVIEW_REJECTED,
    AssistantConversationOutput,
)
from app.application.use_cases.assistant.helpers import (
    conversation_output,
    get_conversation_object,
    read_messages,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType
from app.domain.value_objects.metadata import MetadataEntry, MetadataLayer, Provenance

# The human feedback bounds (Sprint-7 M5): a reviewer's notes are capped
# like the other free-text fields; rating is a 1-5 star scale; confidence
# is a 0..1 fraction. ``None`` means the reviewer gave no rating / no
# confidence / no linked evaluation run.
REVIEW_NOTES_MAX = 2000
REVIEW_RATING_MIN = 1
REVIEW_RATING_MAX = 5


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


@dataclass(frozen=True)
class ReviewDecision:
    """One durable human review action (Sprint-7 M5).

    The audit-history unit of the review workspace: WHO reviewed, WHAT
    they decided, the review status BEFORE the action (so the state
    machine is reconstructible from the log alone), the human feedback
    (notes / rating / confidence), the optional linked evaluation run,
    and the action timestamp. Records are immutable and append-only —
    every action, including re-reviews, appends a new row.
    """

    decision_id: str
    conversation_id: str
    decision: str  # REVIEW_APPROVED | REVIEW_REJECTED
    reviewer: str
    previous_status: str  # the review status before this action ("" when none)
    notes: str = ""
    rating: int | None = None  # 1..5
    confidence: float | None = None  # 0.0..1.0
    eval_run_id: str | None = None
    created_at: str = ""  # ISO-8601

    def __post_init__(self) -> None:
        if not self.decision_id or not self.conversation_id or not self.reviewer:
            raise ValueError("ReviewDecision identity fields must not be empty.")
        if self.decision not in (REVIEW_APPROVED, REVIEW_REJECTED):
            raise ValueError(f"Unknown review decision: {self.decision!r}")
        if len(self.notes) > REVIEW_NOTES_MAX:
            raise ValueError(
                f"ReviewDecision notes must be at most {REVIEW_NOTES_MAX} characters."
            )
        if self.rating is not None and not (
            REVIEW_RATING_MIN <= self.rating <= REVIEW_RATING_MAX
        ):
            raise ValueError(
                f"ReviewDecision rating must be within "
                f"[{REVIEW_RATING_MIN}, {REVIEW_RATING_MAX}]."
            )
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError("ReviewDecision confidence must be within [0.0, 1.0].")
        if self.eval_run_id is not None and not str(self.eval_run_id).strip():
            raise ValueError("ReviewDecision eval_run_id must not be blank.")
        if not self.created_at:
            raise ValueError("ReviewDecision created_at must not be empty.")


@dataclass(frozen=True)
class ReviewQueueItem:
    """One conversation awaiting review (the queue projection)."""

    conversation: AssistantConversationOutput
    question: str
    answer: str
    message_seq: int


def _set_review(obj, status: str) -> None:
    """L1/SYSTEM fact, exactly like intake's system metadata."""
    obj.set_metadata(
        MetadataEntry(
            KEY_REVIEW_STATUS,
            status,
            MetadataLayer.L1_SYSTEM,
            Provenance.SYSTEM,
        ),
        actor="system",
    )


def _review_status(obj) -> str:
    raw = obj.metadata.get_value(KEY_REVIEW_STATUS)
    return raw if raw in (REVIEW_PENDING, REVIEW_APPROVED, REVIEW_REJECTED) else ""


def _latest_assistant_message(obj) -> tuple[int, dict] | None:
    messages = [pair for pair in read_messages(obj) if pair[1].get("role") == "assistant"]
    return messages[-1] if messages else None


class AssistantReviewQueue:
    """The single review-queue seam for assistant answers."""

    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    # ------------------------------------------------------------- lifecycle
    def enqueue(self, conversation_id: str) -> AssistantConversationOutput:
        """Mark the conversation's latest answer as pending review.

        No-op when the conversation has no assistant answer yet (nothing to
        review) or is already pending. Returns the conversation output.
        """
        obj = get_conversation_object(self._repository, conversation_id)
        if _latest_assistant_message(obj) is None or _review_status(obj) == REVIEW_PENDING:
            return conversation_output(obj)
        _set_review(obj, REVIEW_PENDING)
        self._repository.save(obj)
        return conversation_output(obj)

    def approve(self, conversation_id: str) -> AssistantConversationOutput:
        """Approve: the answer becomes visible. Idempotent."""
        obj = get_conversation_object(self._repository, conversation_id)
        if _review_status(obj) != REVIEW_APPROVED:
            _set_review(obj, REVIEW_APPROVED)
            self._repository.save(obj)
        return conversation_output(obj)

    def reject(self, conversation_id: str) -> AssistantConversationOutput:
        """Reject: the answer stays hidden. Idempotent."""
        obj = get_conversation_object(self._repository, conversation_id)
        if _review_status(obj) != REVIEW_REJECTED:
            _set_review(obj, REVIEW_REJECTED)
            self._repository.save(obj)
        return conversation_output(obj)

    # ----------------------------------------------------------------- query
    def pending(self) -> list[ReviewQueueItem]:
        """Every conversation awaiting review, oldest first (deterministic)."""
        objs = self._repository.find_by_metadata(KEY_REVIEW_STATUS, REVIEW_PENDING)
        objs.sort(key=lambda o: str(o.id))
        items: list[ReviewQueueItem] = []
        for obj in objs:
            if obj.object_type is not ObjectType.AI_CONVERSATION:
                continue
            message = _latest_assistant_message(obj)
            if message is None:
                continue
            seq, payload = message
            # The question is the preceding user message (the one this
            # answer responds to).
            user_messages = [
                pair for pair in read_messages(obj) if pair[1].get("role") == "user"
            ]
            question = str(user_messages[-1][1].get("content") or "") if user_messages else ""
            items.append(
                ReviewQueueItem(
                    conversation=conversation_output(obj),
                    question=question,
                    answer=str(payload.get("content") or ""),
                    message_seq=seq,
                )
            )
        return items


__all__ = ["AssistantReviewQueue", "ReviewQueueItem", "_review_status"]
