"""Use case: Load one conversation with its full message thread.

Sprint-6 M5 — human-review gate: when the conversation's latest answer is
PENDING or REJECTED review, the FINAL assistant message is hidden from the
published thread (its answer payload is still stored, so an approval later
makes it visible again). The rest of the thread is unaffected. The gate
only applies when a review status is present — conversations without one
behave exactly as before (backward compatible).
"""
from __future__ import annotations

from app.application.dtos import assistant as dto
from app.application.queries.get_conversation import GetConversationQuery
from app.application.services.assistant_review import _review_status
from app.application.use_cases.assistant.helpers import (
    conversation_output,
    get_conversation_object,
    message_output,
    read_messages,
)
from app.domain.repositories.object_repository import ObjectRepository


class GetConversationUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetConversationQuery) -> dto.ConversationDetailOutput:
        obj = get_conversation_object(self._repository, query.conversation_id)
        messages = [message_output(seq, payload) for seq, payload in read_messages(obj)]
        status = _review_status(obj)
        if status in (dto.REVIEW_PENDING, dto.REVIEW_REJECTED) and messages:
            # The latest assistant answer is not yet approved: hide it from
            # the published thread (the stored payload remains intact).
            messages[-1] = dto.AssistantMessageOutput(
                seq=messages[-1].seq,
                role=messages[-1].role,
                content="",
                created_at=messages[-1].created_at,
                answer=None,
            )
        return dto.ConversationDetailOutput(
            conversation=conversation_output(obj),
            messages=messages,
        )
