"""Use case: Rename / pin / unpin a conversation (verbatim merge).

``title == ""`` clears an explicit rename and hands titling back to the
auto-derived rule (from the first user question).
"""
from __future__ import annotations

from app.application.commands.update_conversation import UpdateConversationCommand
from app.application.dtos import assistant as dto
from app.application.use_cases.assistant.helpers import (
    conversation_output,
    get_conversation_object,
    rename,
    reset_auto_title,
    set_pinned,
)
from app.application.validators.assistant import assert_valid_update_input
from app.domain.repositories.object_repository import ObjectRepository


class UpdateConversationUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: UpdateConversationCommand) -> dto.AssistantConversationOutput:
        assert_valid_update_input(command.input)
        obj = get_conversation_object(self._repository, command.input.conversation_id)
        if command.input.title is not None:
            cleaned = command.input.title.strip()
            if cleaned:
                rename(obj, cleaned)
            else:
                reset_auto_title(obj)
        if command.input.pinned is not None:
            set_pinned(obj, command.input.pinned)
        self._repository.save(obj)
        obj.pop_domain_events()
        return conversation_output(obj)
