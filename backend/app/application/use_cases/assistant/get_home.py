"""Use case: AI Home payload (suggested prompts + recent + pinned threads)."""
from __future__ import annotations

from app.application.dtos import assistant as dto
from app.application.ports.assistant_provider import AssistantProvider
from app.application.queries.get_assistant_home import GetAssistantHomeQuery
from app.application.use_cases.assistant.helpers import home_output
from app.domain.repositories.object_repository import ObjectRepository


class GetAssistantHomeUseCase:
    def __init__(self, repository: ObjectRepository, provider: AssistantProvider) -> None:
        self._repository = repository
        self._provider = provider

    def execute(self, query: GetAssistantHomeQuery) -> dto.AssistantHomeOutput:
        del query
        return home_output(self._repository, self._provider)
