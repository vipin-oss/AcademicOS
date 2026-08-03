"""Use case: Ask the assistant a question.

The heart of the module: resolve (or create) the conversation aggregate, run
the injected ``AssistantProvider`` (rules-v1 in V1 — the future-LLM seam),
append the user + assistant message pair to the thread, persist, and return
the whole exchange. The provider NEVER writes — all persistence happens here,
so a future LLM adapter cannot corrupt the store.
"""
from __future__ import annotations

from app.application.commands.ask_question import AskQuestionCommand
from app.application.dtos import assistant as dto
from app.application.ports.assistant_provider import AssistantProvider
from app.application.use_cases.assistant.helpers import (
    append_message,
    auto_title_if_needed,
    conversation_output,
    create_conversation_object,
    get_conversation_object,
    message_output,
)
from app.application.validators.assistant import assert_valid_ask_input
from app.domain.repositories.object_repository import ObjectRepository


class AskQuestionUseCase:
    def __init__(self, repository: ObjectRepository, provider: AssistantProvider) -> None:
        self._repository = repository
        self._provider = provider

    def execute(self, command: AskQuestionCommand) -> dto.AskOutput:
        assert_valid_ask_input(command.input)
        question = command.input.question.strip()
        if command.input.conversation_id is not None:
            obj = get_conversation_object(self._repository, command.input.conversation_id)
        else:
            obj = create_conversation_object(
                self._repository, "New conversation", command.input.asked_by, title_auto=True
            )
        answer = self._provider.answer(question, command.input.asked_by)
        auto_title_if_needed(obj, question)
        user_seq, user_payload = append_message(obj, "user", question, None)
        assistant_seq, assistant_payload = append_message(
            obj, "assistant", answer.summary, answer
        )
        self._repository.save(obj)
        obj.pop_domain_events()
        return dto.AskOutput(
            conversation=conversation_output(obj),
            user_message=message_output(user_seq, user_payload),
            assistant_message=message_output(assistant_seq, assistant_payload),
            answer=answer,
        )
