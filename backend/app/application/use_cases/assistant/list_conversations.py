"""Use case: List conversations — pinned first, then most recent activity."""
from __future__ import annotations

from app.application.dtos import assistant as dto
from app.application.queries.list_conversations import ListConversationsQuery
from app.application.use_cases.assistant.helpers import (
    all_conversations,
    conversation_output,
    sort_conversations,
)
from app.domain.repositories.object_repository import ObjectRepository


class ListConversationsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListConversationsQuery) -> dto.ConversationListResult:
        page = max(1, query.page)
        page_size = min(100, max(1, query.page_size))
        ordered = sort_conversations(all_conversations(self._repository))
        start = (page - 1) * page_size
        return dto.ConversationListResult(
            items=[conversation_output(obj) for obj in ordered[start:start + page_size]],
            total_count=len(ordered),
            page=page,
            page_size=page_size,
        )
