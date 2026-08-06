"""Use case: Ask the assistant a question (Sprint-6 M1 orchestration).

The execution pipeline (routes remain orchestration-only; this use case is
the orchestrator):

1. authenticate                 — the route's ``get_current_user`` (401)
2. load conversation            — existing ``get_conversation_object`` /
                                 ``create_conversation_object`` helpers
3. retrieve search context      — ``AssistantRetrievalService`` (hybrid search)
4. retrieve graph context       — same service (graph runtime, BFS)
5. merge context                — same service (dedupe, deterministic order)
6. enforce permissions          — applied INSIDE the reused consumers
                                 (search use case + graph runtime gate every
                                 candidate through the R4 evaluator)
7. build provider prompt        — ``AssistantContextBuilder`` (history +
                                 retrieval, budgeted) then
                                 ``AssistantPromptBuilder`` (deterministic
                                 system + user envelope)
8. invoke provider              — the injected ``AssistantProvider``
9. persist assistant response   — existing ``append_message`` + repository
10. return DTO                  — existing ``conversation_output``

Retrieval wiring is optional: without a retrieval service / context
builder the use case behaves exactly as before (provider called without a
context) — backward compatible and graceful.
"""
from __future__ import annotations

from app.application.assistant.context_builder import AssistantContextBuilder
from app.application.assistant.prompt_builder import AssistantPromptBuilder
from app.application.commands.ask_question import AskQuestionCommand
from app.application.dtos import assistant as dto
from app.application.ports.assistant_provider import AssistantProvider
from app.application.services.assistant_retrieval import AssistantRetrievalService
from app.application.use_cases.assistant.helpers import (
    append_message,
    auto_title_if_needed,
    conversation_output,
    create_conversation_object,
    get_conversation_object,
    message_output,
)
from app.application.validators.assistant import assert_valid_ask_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType
from app.domain.value_objects.object_id import ObjectId


class AskQuestionUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        provider: AssistantProvider,
        *,
        retrieval: AssistantRetrievalService | None = None,
        context_builder: AssistantContextBuilder | None = None,
        prompt_builder: AssistantPromptBuilder | None = None,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._retrieval = retrieval
        self._context_builder = context_builder
        self._prompt_builder = prompt_builder

    def execute(self, command: AskQuestionCommand) -> dto.AskOutput:
        assert_valid_ask_input(command.input)
        question = command.input.question.strip()
        if command.input.conversation_id is not None:
            obj = get_conversation_object(self._repository, command.input.conversation_id)
        else:
            obj = create_conversation_object(
                self._repository, "New conversation", command.input.asked_by, title_auto=True
            )
        context = self._build_context(obj, question, command.input.asked_by)
        prompt = self._build_prompt(question, context)
        kwargs = {"context": context} if context is not None else {}
        if prompt is not None:
            kwargs["prompt"] = prompt
        answer = self._provider.answer(question, command.input.asked_by, **kwargs)
        auto_title_if_needed(obj, question)
        user_seq, user_payload = append_message(obj, "user", question, None)
        assistant_seq, assistant_payload = append_message(
            obj, "assistant", answer.summary, answer
        )
        self._repository.save(obj)
        return dto.AskOutput(
            conversation=conversation_output(obj),
            user_message=message_output(user_seq, user_payload),
            assistant_message=message_output(assistant_seq, assistant_payload),
            answer=answer,
        )

    # ------------------------------------------------------------- pipeline
    def _build_prompt(
        self, question: str, context: dto.AssistantContext | None
    ) -> dto.AssistantPrompt | None:
        """Step 5 — build the provider prompt (Prompt Builder owns it).

        ``None`` when the builder is not wired or there is no context: the
        provider is then called without a prompt (backward compatible).
        """
        if self._prompt_builder is None or context is None:
            return None
        return self._prompt_builder.build(question, context)

    def _build_context(
        self,
        conversation: UniversalObject,
        question: str,
        asked_by: str,
    ) -> dto.AssistantContext | None:
        """Steps 3-7 of the pipeline: retrieve, merge, build the envelope.

        Returns ``None`` when retrieval is not wired or the asker is not a
        real USER object (tests / system asks) — the call then degrades to
        the pre-S6 provider call.
        """
        if self._retrieval is None or self._context_builder is None:
            return None
        asker = self._repository.get_by_id(ObjectId(asked_by))
        if asker is None or asker.object_type is not ObjectType.USER:
            return None  # no retrievable principal
        result = self._retrieval.retrieve(question, asker)
        return self._context_builder.build(conversation, question, result)
