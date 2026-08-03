"""Use case: Load one conversation with its full message thread."""
from __future__ import annotations

from app.application.dtos import assistant as dto
from app.application.queries.get_conversation import GetConversationQuery
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
        return dto.ConversationDetailOutput(
            conversation=conversation_output(obj),
            messages=messages,
        )
