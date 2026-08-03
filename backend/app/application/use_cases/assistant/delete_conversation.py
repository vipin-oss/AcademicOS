"""Use case: Delete a conversation (and its embedded message thread)."""
from __future__ import annotations

from app.application.commands.delete_conversation import DeleteConversationCommand
from app.application.use_cases.assistant.helpers import get_conversation_object
from app.application.validators.assistant import assert_valid_delete_input
from app.domain.repositories.object_repository import ObjectRepository


class DeleteConversationUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: DeleteConversationCommand) -> None:
        assert_valid_delete_input(command.input)
        obj = get_conversation_object(self._repository, command.input.conversation_id)
        self._repository.delete(obj.id)
