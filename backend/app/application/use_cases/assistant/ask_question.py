"""Use case: Ask the assistant a question (Sprint-6 M1 orchestration).

The execution pipeline (routes remain orchestration-only; this use case is
the orchestrator):

1. authenticate                 — the route's ``get_current_user`` (401)
2. load conversation            — existing ``get_conversation_object`` /
                                 ``create_conversation_object`` helpers
3. retrieve search context      — ``AssistantRetrievalService`` (hybrid search)
4. retrieve graph context       — same service (graph runtime, BFS)
5. merge context                — same service (dedupe, deterministic order)
5b. recall memory               — AssistantMemoryService (Sprint-8 M2):
                                 prior conversations + graph knowledge,
                                 current thread excluded; rendered as
                                 distinct prompt sections by the Prompt
                                 Builder
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

from dataclasses import asdict

from app.application.assistant.citations import CitationBuilder
from app.application.assistant.context_builder import AssistantContextBuilder
from app.application.assistant.prompt_builder import AssistantPromptBuilder
from app.application.assistant.verifier import AnswerVerifier
from app.application.commands.ask_question import AskQuestionCommand
from app.application.dtos import assistant as dto
from app.application.ports.assistant_memory import AssistantMemoryRetriever
from app.application.ports.assistant_provider import AssistantProvider
from app.application.services.assistant_retrieval import AssistantRetrievalService
from app.application.services.assistant_review import AssistantReviewQueue
from app.application.services.model_registry import ModelRegistry, resolve_model
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
        citation_builder: CitationBuilder | None = None,
        verifier: AnswerVerifier | None = None,
        review_queue: AssistantReviewQueue | None = None,
        registry: ModelRegistry | None = None,
        provider_factory=None,
        memory: AssistantMemoryRetriever | None = None,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._retrieval = retrieval
        self._context_builder = context_builder
        self._prompt_builder = prompt_builder
        self._citation_builder = citation_builder
        self._verifier = verifier
        self._review_queue = review_queue
        self._registry = registry
        self._provider_factory = provider_factory
        self._memory = memory

    def execute(self, command: AskQuestionCommand) -> dto.AskOutput:
        """Normal mode — the synchronous pipeline (Sprint-6 M1-M3), with
        model selection (Sprint-7 M2)."""
        assert_valid_ask_input(command.input)
        obj, question, asked_by = self._prepare(command)
        provider = self._select_provider(obj, command.input.model_id)
        _context, citations, kwargs = self._call_kwargs(obj, question, asked_by)
        answer = provider.answer(question, asked_by, **kwargs)
        return self._finalize(obj, question, answer, citations, asked_by)

    def stream(self, command: AskQuestionCommand):
        """Stream mode — the SAME orchestration path, yielding SSE events.

        Yields ``{"event": "token", "data": {"delta": ...}}`` for every
        partial chunk, then exactly one ``{"event": "completion", ...}``
        whose data mirrors the synchronous ``AskOutput`` shape (conversation,
        user_message, assistant_message, answer). Citation verification and
        conversation persistence happen BEFORE the completion is yielded, so
        partial tokens are never stored. On failure an
        ``{"event": "error", "data": {"message": ...}}`` is yielded and
        nothing is persisted. When the provider cannot stream, a single
        token event carries the whole deterministic answer (additive).
        """
        assert_valid_ask_input(command.input)
        obj, question, asked_by = self._prepare(command)
        provider = self._select_provider(obj, command.input.model_id)
        _context, citations, kwargs = self._call_kwargs(obj, question, asked_by)
        stream_fn = getattr(provider, "stream", None)
        if stream_fn is None:
            # Provider cannot stream: a deterministic single completion.
            answer = provider.answer(question, asked_by, **kwargs)
            yield {"event": "token", "data": {"delta": answer.summary}}
        else:
            try:
                for event in stream_fn(question, asked_by, **kwargs):
                    if event["type"] == "token":
                        yield {"event": "token", "data": {"delta": event["delta"]}}
                    elif event["type"] == "complete":
                        answer = event["answer"]
            except Exception as exc:  # noqa: BLE001 — stream failures surface as an error event
                yield {"event": "error", "data": {"message": str(exc)}}
                return
        yield self._completion_event(obj, question, answer, citations, asked_by)

    # ------------------------------------------------------------- shared
    def _prepare(self, command: AskQuestionCommand):
        """Step 2 — load or create the conversation aggregate."""
        if command.input.conversation_id is not None:
            obj = get_conversation_object(self._repository, command.input.conversation_id)
        else:
            obj = create_conversation_object(
                self._repository, "New conversation", command.input.asked_by, title_auto=True
            )
        if self._registry is not None and command.input.model_id is not None:
            # An explicit override re-pins the conversation.
            self._bind_model(obj, command.input.model_id)
        return obj, command.input.question.strip(), command.input.asked_by

    def _bind_model(self, obj: UniversalObject, requested_model_id: str | None) -> None:
        """Pin the resolved model on the conversation (S7 M2).

        The resolved model (override or registry default) becomes the
        conversation's model, stored as L1/SYSTEM metadata, persisting
        across follow-ups. An explicit override always wins and re-pins.
        """
        current = obj.metadata.get_value(dto.KEY_MODEL_ID)
        if current and not requested_model_id:
            return  # already pinned; no override requested
        spec = resolve_model(
            self._registry,  # type: ignore[arg-type]
            conversation_model_id=current or None,
            requested_model_id=requested_model_id,
        )
        if current == spec.id:
            return
        from app.domain.value_objects.metadata import (
            MetadataEntry,
            MetadataLayer,
            Provenance,
        )

        obj.set_metadata(
            MetadataEntry(
                dto.KEY_MODEL_ID, spec.id, MetadataLayer.L1_SYSTEM, Provenance.SYSTEM
            ),
            actor="system",
        )

    def _select_provider(self, obj: UniversalObject, requested_model_id: str | None):
        """The provider for THIS ask (S7 M2).

        Registry-driven: resolve the model (override > pin > default) and
        build the provider via the shared factory. Without a registry the
        injected default provider is used (backward compatible). Sync and
        streaming both call this — identical selection.
        """
        if self._registry is None or self._provider_factory is None:
            return self._provider
        pinned = obj.metadata.get_value(dto.KEY_MODEL_ID)
        if not requested_model_id and not pinned and self._provider is not None:
            # No pin, no override: the injected provider (the route's
            # default) is authoritative — this preserves the pre-M2 path
            # exactly, including test overrides. With no injected provider
            # (registry-only wiring) the registry default drives selection.
            return self._provider
        model_id = requested_model_id or pinned
        spec = resolve_model(
            self._registry, conversation_model_id=model_id, requested_model_id=requested_model_id
        )
        provider = self._provider_factory(spec, self._repository)
        # The registry drove selection: record the pin so follow-ups reuse
        # the same model (S7 M2).
        if not pinned:
            self._bind_model(obj, spec.id)
        return provider

    def _call_kwargs(
        self, obj: UniversalObject, question: str, asked_by: str
    ) -> tuple[None | dto.AssistantContext, tuple[dto.AssistantCitation, ...], dict]:
        """Steps 3-7 — retrieve, merge, build context + citations + prompt."""
        context = self._build_context(obj, question, asked_by)
        citations = self._build_citations(context)
        prompt = self._build_prompt(question, context, citations)
        kwargs = {"context": context} if context is not None else {}
        if prompt is not None:
            kwargs["prompt"] = prompt
        return context, citations, kwargs

    def _finalize(
        self,
        obj: UniversalObject,
        question: str,
        answer: dto.AssistantAnswerOutput,
        citations: tuple[dto.AssistantCitation, ...],
        asked_by: str,
    ) -> dto.AskOutput:
        """Steps 9-10 — verify citations, persist, return the DTO.

        Citation verification ALWAYS happens before persistence (S6 M3);
        persistence happens only for the final, verified answer — partial
        tokens are never stored.
        """
        self._attach_verified_citations(answer, citations, asked_by)
        auto_title_if_needed(obj, question)
        user_seq, user_payload = append_message(obj, "user", question, None)
        assistant_seq, assistant_payload = append_message(
            obj, "assistant", answer.summary, answer
        )
        self._repository.save(obj)
        if self._review_queue is not None:
            # Human review gate (S6 M5): the freshly produced answer is
            # stored but not visible until approved. Sync and stream share
            # this single finalize path.
            self._review_queue.enqueue(str(obj.id))
        return dto.AskOutput(
            conversation=conversation_output(obj),
            user_message=message_output(user_seq, user_payload),
            assistant_message=message_output(assistant_seq, assistant_payload),
            answer=answer,
        )

    def _completion_event(
        self,
        obj: UniversalObject,
        question: str,
        answer: dto.AssistantAnswerOutput,
        citations: tuple[dto.AssistantCitation, ...],
        asked_by: str,
    ) -> dict:
        """The terminal SSE event: verified answer + persisted conversation
        in the same shape the synchronous endpoint returns."""
        out = self._finalize(obj, question, answer, citations, asked_by)
        return {
            "event": "completion",
            "data": {
                "conversation": asdict(out.conversation),
                "user_message": asdict(out.user_message),
                "assistant_message": asdict(out.assistant_message),
                "answer": asdict(out.answer),
            },
        }

    # ------------------------------------------------------------- pipeline
    def _build_prompt(
        self,
        question: str,
        context: dto.AssistantContext | None,
        citations: tuple[dto.AssistantCitation, ...] = (),
    ) -> dto.AssistantPrompt | None:
        """Step 5 — build the provider prompt (Prompt Builder owns it).

        ``None`` when the builder is not wired or there is no context: the
        provider is then called without a prompt (backward compatible).
        The numbered citations travel with the prompt (S6 M3).
        """
        if self._prompt_builder is None or context is None:
            return None
        return self._prompt_builder.build(question, context, citations=citations)

    # ------------------------------------------------------------- citations
    def _build_citations(
        self, context: dto.AssistantContext | None
    ) -> tuple[dto.AssistantCitation, ...]:
        """Number the permission-filtered retrieval items (S6 M3)."""
        if self._citation_builder is None or context is None:
            return ()
        return self._citation_builder.build(context.retrieved)

    def _attach_verified_citations(
        self,
        answer: dto.AssistantAnswerOutput,
        citations: tuple[dto.AssistantCitation, ...],
        asked_by: str,
    ) -> None:
        """Post-provider verification (S6 M3 Phase 5): every citation must
        reference an existing, READ-permitted object; invalid ones are
        dropped and survivors renumbered. Evidence cards fill the answer
        only when the provider produced none (LLM path) — rules-provider
        cards are never clobbered."""
        if not citations or self._verifier is None:
            return
        asker = self._load_asker(asked_by)
        if asker is None or asker.object_type is not ObjectType.USER:
            return
        verified = self._verifier.verify(citations, self._repository, asker)
        answer.citations = list(verified)
        if self._citation_builder is not None and not answer.cards:
            answer.cards = self._citation_builder.evidence_cards(verified)

    def _load_asker(self, asked_by: str) -> UniversalObject | None:
        try:
            return self._repository.get_by_id(ObjectId(asked_by))
        except ValueError:
            return None

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
        # Sprint-8 M2 — memory-augmented asks: automatically recall prior
        # conversations (and their graph-discovered knowledge) through the
        # SAME memory service the recall endpoint exposes. The current
        # conversation is excluded — its history is already in the prompt.
        memory_recall = None
        if self._memory is not None:
            memory_recall = self._memory.recall(
                question,
                asker,
                exclude_conversation_id=str(conversation.id),
            )
        return self._context_builder.build(
            conversation, question, result, memory=memory_recall
        )
