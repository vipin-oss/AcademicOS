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

from dataclasses import dataclass

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
