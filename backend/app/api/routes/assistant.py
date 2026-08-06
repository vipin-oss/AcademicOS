"""REST routes for the Academic Intelligence Assistant (Module 13).

Mirrors ``routes/settings.py`` / ``routes/productivity.py`` one-to-one: thin
request models (extra=forbid), ``_unprocessable``/``_not_found`` mapping,
dual PUT+PATCH decorators on the update endpoint, and static paths declared
before parameterized ones.

The provider dependency — :func:`get_assistant_provider` — is THE future-LLM
swap point: V1 wires the local deterministic ``RuleBasedAssistantProvider``;
a sanctioned LLM adapter later replaces this single function without touching
routes, use cases, or contracts (the FileStorage doctrine applied to
intelligence). No external AI is called anywhere in V1.

Surface:
    GET    /assistant/home                       AI Home payload (suggested +
                                                 recent + pinned)
    POST   /assistant/ask                        ask a question (answer +
                                                 persisted message pair)
    GET    /assistant/suggested                  suggested questions catalogue
    GET    /assistant/conversations              list (pinned first)
    POST   /assistant/conversations              start an empty conversation
    GET    /assistant/conversations/{id}         full message thread
    PUT|PATCH /assistant/conversations/{id}      rename / pin / unpin
    DELETE /assistant/conversations/{id}         delete (204)
"""
from __future__ import annotations

import json
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.mappers.assistant_mapper import (
    output_dict,
    to_ask_input,
    to_create_input,
    to_delete_input,
    to_update_input,
)
from app.api.routes.eval_history import get_eval_history
from app.api.routes.search import get_embedder, get_vector_repository
from app.application.assistant.citations import CitationBuilder
from app.application.assistant.context_builder import AssistantContextBuilder
from app.application.assistant.prompt_builder import (
    SYSTEM_INSTRUCTIONS,
    AssistantPromptBuilder,
)
from app.application.assistant.verifier import AnswerVerifier
from app.application.commands.ask_question import AskQuestionCommand
from app.application.commands.create_conversation import CreateConversationCommand
from app.application.commands.delete_conversation import DeleteConversationCommand
from app.application.commands.update_conversation import UpdateConversationCommand
from app.application.dtos.assistant import INTENT_GROUPS, INTENT_LABELS, SUGGESTED_QUESTIONS
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.assistant_provider import AssistantProvider
from app.application.ports.embedder import Embedder
from app.application.queries.get_assistant_home import GetAssistantHomeQuery
from app.application.queries.get_conversation import GetConversationQuery
from app.application.queries.list_conversations import ListConversationsQuery
from app.application.services.assistant_eval import EvaluationHistory
from app.application.services.assistant_memory import AssistantMemoryService
from app.application.services.assistant_retrieval import AssistantRetrievalService
from app.application.services.assistant_review import (
    REVIEW_NOTES_MAX,
    REVIEW_RATING_MAX,
    REVIEW_RATING_MIN,
    AssistantReviewQueue,
)
from app.application.services.graph_runtime import GraphRuntimeService
from app.application.services.memory_consolidation import MemoryConsolidationService
from app.application.services.model_registry import registry_from_settings
from app.application.services.prompt_registry import DEFAULT_PROMPT_ID, PromptAsset, PromptRegistry
from app.application.use_cases.assistant.ask_question import AskQuestionUseCase
from app.application.use_cases.assistant.create_conversation import CreateConversationUseCase
from app.application.use_cases.assistant.delete_conversation import DeleteConversationUseCase
from app.application.use_cases.assistant.get_conversation import GetConversationUseCase
from app.application.use_cases.assistant.get_home import GetAssistantHomeUseCase
from app.application.use_cases.assistant.list_conversations import ListConversationsUseCase
from app.application.use_cases.assistant.update_conversation import UpdateConversationUseCase
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.core.config import settings
from app.domain.entities.object import UniversalObject
from app.domain.repositories.vector_repository import VectorRepository
from app.infrastructure.assistant.provider_factory import build_provider
from app.infrastructure.db.session import get_db
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.persistence.review_decision_store import (
    SQLReviewDecisionStore,
)
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.repositories.sqlalchemy_search_repository import (
    SQLAlchemySearchRepository,
)

router = APIRouter(prefix="/assistant", tags=["Assistant"], dependencies=[Depends(get_current_user)])


def _repository(db: Session = Depends(get_db)) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


def get_assistant_provider(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> AssistantProvider:
    """Composition seam (Sprint-7 M1): the MODEL REGISTRY is the single
    source of truth — the default registered model is looked up and the
    provider is built by the shared factory (``build_provider``). No
    provider construction lives in the route. Integration tests override
    this dependency to inject stubs/transports."""
    registry = registry_from_settings(settings)
    return build_provider(registry.default(), repo)


def get_assistant_provider_factory():
    """The provider factory used for per-conversation model selection
    (Sprint-7 M2). Overridable in tests to inject transports."""
    return build_provider


def get_assistant_retrieval(
    db: Session = Depends(get_db),
    vector_repository: VectorRepository | None = Depends(get_vector_repository),
    embedder: Embedder = Depends(get_embedder),
) -> AssistantRetrievalService:
    """Composition seam for the S6 M1 retrieval pipeline: hybrid search +
    graph runtime, both gated by the shared R4 evaluator. The semantic leg
    reuses the search route's overrideable dependencies and degrades to
    lexical when unavailable."""
    search = SearchObjectsUseCase(
        search_repository=SQLAlchemySearchRepository(db),
        object_repository=SQLAlchemyObjectRepository(db),
        permission_evaluator=ObjectPermissionEvaluator(),
        vector_repository=vector_repository,
        embedder=embedder,
    )
    graph = GraphRuntimeService(SQLAlchemyObjectRepository(db), ObjectPermissionEvaluator())
    return AssistantRetrievalService(search, graph)


def get_assistant_memory(
    db: Session = Depends(get_db),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    retrieval: AssistantRetrievalService = Depends(get_assistant_retrieval),
) -> AssistantMemoryService:
    """Composition seam (Sprint-8 M1/M3): assistant memory over the SAME
    retrieval pipeline as the ask flow. Sprint-8 M3 — the review-decision
    store (S7 M5) is wired so recalled memories are re-ranked by human
    review history. Overridable in tests."""
    return AssistantMemoryService(
        repo, retrieval, decision_store=SQLReviewDecisionStore(db)
    )


def _not_found(exc: ObjectNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _unprocessable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
    )


# ---------------------------------------------------------------------------
# Request models (extra=forbid, module doctrine)
# ---------------------------------------------------------------------------
class StrictBody(BaseModel):
    # ``model_id`` (S7 M2) collides with pydantic's "model_" protected
    # namespace — disabled like the other assistant body fields.
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


class AskBody(StrictBody):
    question: str
    conversation_id: str | None = None
    asked_by: str | None = None
    model_id: str | None = None  # S7 M2: per-request model override


class CreateConversationBody(StrictBody):
    title: str | None = None
    created_by: str | None = None


class UpdateConversationBody(StrictBody):
    # strict: the verbatim merge must not silently coerce ("false" -> True)
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str | None = None
    pinned: bool | None = None
    updated_by: str | None = None


# ---------------------------------------------------------------------------
# AI Home / asking / suggestions (static paths first)
# ---------------------------------------------------------------------------
@router.get("/home")
def get_home(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    provider: AssistantProvider = Depends(get_assistant_provider),
):
    out = GetAssistantHomeUseCase(repo, provider).execute(GetAssistantHomeQuery())
    return output_dict(out)


@router.post("/ask", status_code=status.HTTP_201_CREATED)
def ask_question(
    body: AskBody,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    provider: AssistantProvider = Depends(get_assistant_provider),
    retrieval: AssistantRetrievalService = Depends(get_assistant_retrieval),
    provider_factory=Depends(get_assistant_provider_factory),
    memory: AssistantMemoryService = Depends(get_assistant_memory),
    user: UniversalObject = Depends(get_current_user),
):
    try:
        out = _ask_use_case(repo, provider, retrieval, provider_factory, memory).execute(
            AskQuestionCommand(input=to_ask_input({**body.model_dump(), "asked_by": str(user.id)}))
        )
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except KeyError as exc:
        # S7 M2: an unknown model override is a client error (422).
        raise _unprocessable(exc) from exc
    return output_dict(out)


def _ask_use_case(
    repo: SQLAlchemyObjectRepository,
    provider: AssistantProvider,
    retrieval: AssistantRetrievalService,
    provider_factory=None,
    memory: AssistantMemoryService | None = None,
) -> AskQuestionUseCase:
    """One construction site for the ask pipeline (sync and stream modes)."""
    prompt_registry = _default_prompt_registry()
    return AskQuestionUseCase(
        repo,
        provider,
        retrieval=retrieval,
        context_builder=AssistantContextBuilder(),
        prompt_builder=AssistantPromptBuilder(prompt_registry=prompt_registry),
        # S8 M2: memory-augmented asks — prior conversations are recalled
        # before answering and become distinct prompt sections.
        memory=memory,
        # S7 M2: the model registry drives per-conversation selection.
        registry=registry_from_settings(settings),
        provider_factory=provider_factory or build_provider,
        citation_builder=CitationBuilder(),
        verifier=AnswerVerifier(ObjectPermissionEvaluator()),
        # Human review gate (S6 M5): when enabled, every fresh answer is
        # stored PENDING and only becomes visible after approval. Sync and
        # stream share this wiring through the one construction site.
        review_queue=(
            AssistantReviewQueue(repo) if settings.assistant_review_enabled else None
        ),
    )


def _default_prompt_registry() -> PromptRegistry:
    """The default prompt registry: the assistant.default asset v1 carries
    the canonical system instructions (Sprint-7 M1, AI doc A7.1)."""
    registry = PromptRegistry()
    registry.register(
        PromptAsset(
            id=DEFAULT_PROMPT_ID,
            version=1,
            version_label="1.0",
            owner="assistant",
            system_text=SYSTEM_INSTRUCTIONS,
        )
    )
    return registry


def _sse(event: str, data: dict) -> str:
    """One Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/ask/stream")
def ask_question_stream(
    body: AskBody,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    provider: AssistantProvider = Depends(get_assistant_provider),
    retrieval: AssistantRetrievalService = Depends(get_assistant_retrieval),
    provider_factory=Depends(get_assistant_provider_factory),
    memory: AssistantMemoryService = Depends(get_assistant_memory),
    user: UniversalObject = Depends(get_current_user),
):
    """Streaming ask (Sprint-6 M4): Server-Sent Events over the SAME
    pipeline as ``POST /ask``. Events: ``token`` (partial deltas),
    ``completion`` (verified answer + persisted conversation, mirroring
    the sync response shape) or ``error`` (nothing persisted). The client
    can disconnect at any time — partial tokens are never stored."""
    use_case = _ask_use_case(repo, provider, retrieval, provider_factory, memory)
    command = AskQuestionCommand(
        input=to_ask_input({**body.model_dump(), "asked_by": str(user.id)})
    )
    from app.application.services.model_registry import resolve_model
    from app.application.validators.assistant import assert_valid_ask_input

    try:
        assert_valid_ask_input(command.input)
        # Eager model validation (S7 M2): an unknown override fails fast
        # with 422 instead of mid-stream. The registry is the single source
        # of truth; conversation pinning happens inside the stream itself.
        if command.input.model_id:
            resolve_model(registry_from_settings(settings), requested_model_id=command.input.model_id)
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    except KeyError as exc:
        raise _unprocessable(exc) from exc

    def events():
        for event in use_case.stream(command):
            yield _sse(event["event"], event["data"])

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/memory/recall")
def memory_recall(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(10, ge=1, le=50),
    memory: AssistantMemoryService = Depends(get_assistant_memory),
    user: UniversalObject = Depends(get_current_user),
):
    """Assistant memory recall (Sprint-8 M1): prior conversations relevant
    to ``q`` — the latest question/answer pair with the preserved
    citations (review-gated: pending/rejected answers are recalled with
    empty content) — plus the graph-discovered related knowledge objects.
    Deterministic ordering; bounded by ``limit``."""
    out = memory.recall(q, user, limit=limit)
    return {
        "conversations": [asdict(item) for item in out.conversations],
        "knowledge": [asdict(item) for item in out.knowledge],
        "search_count": out.search_count,
        "graph_count": out.graph_count,
    }


@router.post("/memory/consolidate")
def consolidate_memory(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
):
    """One memory-consolidation pass (Sprint-8 M4): redundant
    conversations are marked SUPERSEDED by their canonical memory —
    nothing is ever deleted, and consolidated memories disappear from
    recall by default. Mirrors the search index-sync action pattern."""
    report = MemoryConsolidationService(repo).consolidate(actor=str(user.id))
    return {
        "scanned": report.scanned,
        "consolidated": report.consolidated,
        "superseded": [
            {
                "conversation_id": pair.conversation_id,
                "canonical_id": pair.canonical_id,
            }
            for pair in report.superseded
        ],
    }


@router.get("/suggested")
def get_suggested():
    """The deterministic suggestion catalogue (with the intent taxonomy)."""
    return {
        "suggested": [
            {"group": group, "question": question, "intent": intent}
            for group, question, intent in SUGGESTED_QUESTIONS
        ],
        "intents": [
            {"group": group, "codes": [{"code": code, "label": INTENT_LABELS[code]} for code in codes]}
            for group, codes in INTENT_GROUPS
        ],
    }


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------
@router.get("/conversations")
def list_conversations(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    out = ListConversationsUseCase(repo).execute(
        ListConversationsQuery(page=page, page_size=page_size)
    )
    return output_dict(out)


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
def create_conversation(
    body: CreateConversationBody,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
):
    try:
        out = CreateConversationUseCase(repo).execute(
            CreateConversationCommand(input=to_create_input({**body.model_dump(), "created_by": str(user.id)}))
        )
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    return output_dict(out)


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        out = GetConversationUseCase(repo).execute(
            GetConversationQuery(conversation_id=conversation_id)
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return output_dict(out)


def _update_conversation(
    conversation_id: str,
    body: UpdateConversationBody,
    repo: SQLAlchemyObjectRepository,
    user: UniversalObject,
):
    try:
        out = UpdateConversationUseCase(repo).execute(
            UpdateConversationCommand(input=to_update_input(conversation_id, {**body.model_dump(), "updated_by": str(user.id)}))
        )
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return output_dict(out)




@router.put("/conversations/{conversation_id}")
@router.patch("/conversations/{conversation_id}")
def update_conversation(
    conversation_id: str,
    body: UpdateConversationBody,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
):
    return _update_conversation(conversation_id, body, repo, user)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    try:
        DeleteConversationUseCase(repo).execute(
            DeleteConversationCommand(input=to_delete_input(conversation_id))
        )
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc


# ---------------------------------------------------------------------------
# Review queue (Sprint-6 M5) — human approval before publication
# ---------------------------------------------------------------------------
@router.get("/review/pending")
def review_pending(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
):
    """Every conversation awaiting human review, oldest first. The queue is
    a projection over the conversation objects (no separate storage)."""
    items = AssistantReviewQueue(repo).pending()
    return {
        "items": [
            {
                "conversation": asdict(item.conversation),
                "question": item.question,
                "answer": item.answer,
                "message_seq": item.message_seq,
            }
            for item in items
        ]
    }


class ReviewActionBody(StrictBody):
    """The human review action (Sprint-7 M5 — human feedback loop).

    ``conversation_id`` alone remains valid (backward compatible); the
    feedback fields are optional: reviewer notes, a 1-5 rating, a 0-1
    confidence, and an optional linked evaluation run (validated against
    the evaluation history — an unknown run id is a client error)."""

    conversation_id: str
    notes: str | None = Field(None, max_length=REVIEW_NOTES_MAX)
    rating: int | None = Field(None, ge=REVIEW_RATING_MIN, le=REVIEW_RATING_MAX)
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    eval_run_id: str | None = Field(None, max_length=64)


def _review_queue(
    repo: SQLAlchemyObjectRepository, db: Session
) -> AssistantReviewQueue:
    """The workspace queue: state transitions on the conversation objects
    plus the durable audit trail (Sprint-7 M5)."""
    return AssistantReviewQueue(
        repo, decision_store=SQLReviewDecisionStore(db)
    )


def _validated_eval_run(
    eval_run_id: str | None,
    history: EvaluationHistory,
) -> str | None:
    """The eval-run link must reference a recorded run (Sprint-7 M5): an
    unknown id is a client error (422), never a broken link. Reuses the
    evaluation-history dependency — no duplicated evaluation logic."""
    if eval_run_id is None:
        return None
    if history.get(eval_run_id) is None:
        raise _unprocessable(ValueError(f"Unknown evaluation run: {eval_run_id}"))
    return eval_run_id


def _review_response(out) -> dict:
    """The workspace action response: the conversation output (unchanged
    shape) plus the recorded audit decision (None when not recorded)."""
    return {
        "conversation": asdict(out.conversation),
        "decision": asdict(out.decision) if out.decision is not None else None,
    }


@router.post("/review/approve")
def review_approve(
    body: ReviewActionBody,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
    history: EvaluationHistory = Depends(get_eval_history),
):
    """Approve a conversation's latest answer: it becomes visible. Records
    the review decision (reviewer = the authenticated user) with the
    optional notes / rating / confidence / evaluation-run link."""
    eval_run_id = _validated_eval_run(body.eval_run_id, history)
    try:
        out = _review_queue(repo, db).approve(
            body.conversation_id,
            reviewer=str(user.id),
            notes=body.notes or "",
            rating=body.rating,
            confidence=body.confidence,
            eval_run_id=eval_run_id,
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return _review_response(out)


@router.post("/review/reject")
def review_reject(
    body: ReviewActionBody,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
    history: EvaluationHistory = Depends(get_eval_history),
):
    """Reject a conversation's latest answer: it stays hidden. Records the
    review decision with the optional feedback fields."""
    eval_run_id = _validated_eval_run(body.eval_run_id, history)
    try:
        out = _review_queue(repo, db).reject(
            body.conversation_id,
            reviewer=str(user.id),
            notes=body.notes or "",
            rating=body.rating,
            confidence=body.confidence,
            eval_run_id=eval_run_id,
        )
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return _review_response(out)


@router.get("/review/decisions")
def review_decisions(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
):
    """The workspace activity feed: the most recent review decisions,
    newest first (Sprint-7 M5)."""
    items = _review_queue(repo, db).recent_decisions(limit)
    return {"items": [asdict(item) for item in items]}


@router.get("/review/decisions/{conversation_id}")
def review_decisions_for_conversation(
    conversation_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    db: Session = Depends(get_db),
):
    """The complete audit trail of one conversation, oldest first —
    every decision ever taken on it, including re-reviews (Sprint-7 M5).
    Empty when the conversation has never been reviewed."""
    items = _review_queue(repo, db).decisions(conversation_id)
    return {"items": [asdict(item) for item in items]}
