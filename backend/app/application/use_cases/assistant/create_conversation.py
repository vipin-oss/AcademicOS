"""Use case: Start a new (empty) assistant conversation."""
from __future__ import annotations

from app.application.commands.create_conversation import CreateConversationCommand
from app.application.dtos import assistant as dto
from app.application.use_cases.assistant.helpers import (
    conversation_output,
    create_conversation_object,
)
from app.application.validators.assistant import assert_valid_create_input
from app.domain.repositories.object_repository import ObjectRepository

PLACEHOLDER_TITLE = "New conversation"


class CreateConversationUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: CreateConversationCommand) -> dto.AssistantConversationOutput:
        assert_valid_create_input(command.input)
        explicit = command.input.title is not None
        title = (command.input.title or "").strip() or PLACEHOLDER_TITLE
        obj = create_conversation_object(
            self._repository,
            title,
            command.input.created_by,
            title_auto=not explicit,
        )
        return conversation_output(obj)
