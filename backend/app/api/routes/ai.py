"""AI Core REST routes (Sprint M11.1 — AI Foundation).

Read-only health surface over the composed AI Core:

    GET /ai/health      aggregate status (public, like /api/v1/health)
    GET /ai/providers   provider catalogue with configuration status
    GET /ai/models      aggregated model catalogue + defaults
    POST /ai/summarize  on-demand document summary (M12.1, feature-flagged)

All three are JSON-only and deterministic. The routes stay
orchestration-free: each endpoint delegates to the matching use case.
Providers/models are configuration-derived, so they require
authentication; the health probe is intentionally public (liveness).

A later M11 sprint adds generation endpoints that consume
``core.gateway(...)`` — this module will not change shape.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.dependencies.ai import get_ai_core
from app.api.dependencies.auth import get_current_user
from app.api.routes.documents import get_storage
from app.api.routes.search import get_embedder, get_vector_repository
from app.application.ai.core import AiCore
from app.application.assistant.citations import CitationBuilder
from app.application.assistant.prompt_builder import AssistantPromptBuilder
from app.application.assistant.verifier import AnswerVerifier
from app.application.dtos.ai import (
    domain_assistant_result_dict,
    enrichment_result_dict,
    handoff_bundle_dict,
    health_summary_dict,
    models_summary_dict,
    provider_record_dict,
    qa_result_dict,
    related_documents_result_dict,
    summarize_result_dict,
)
from app.application.exceptions import (
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.application.ports.embedder import Embedder
from app.application.services.assistant_retrieval import AssistantRetrievalService
from app.application.services.document_annotation_service import (
    DocumentAnnotationService,
)
from app.application.services.graph_runtime import GraphRuntimeService
from app.application.services.outbox import to_outbox_row
from app.application.use_cases.ai.chat import CHAT_SYSTEM_INSTRUCTIONS, ChatTurn, ChatUseCase
from app.application.use_cases.ai.domain_assistant import (
    ASSISTANT_ROLE_KEYS,
    ASSISTANT_ROLES,
    DomainAssistantRole,
    DomainAssistantUseCase,
)
from app.application.use_cases.ai.enrich_document import EnrichDocumentUseCase
from app.application.use_cases.ai.get_ai_health import GetAiHealthUseCase
from app.application.use_cases.ai.grounded_qa import DEFAULT_MAX_OUTPUT_TOKENS, GroundedQAUseCase
from app.application.use_cases.ai.handoff import SUPPORTED_TASKS, HandoffUseCase
from app.application.use_cases.ai.list_ai_models import ListAiModelsUseCase
from app.application.use_cases.ai.list_ai_providers import ListAiProvidersUseCase
from app.application.use_cases.ai.related_documents import RelatedDocumentsUseCase
from app.application.use_cases.ai.rung0 import Rung0ClaimAnswerer
from app.application.use_cases.ai.summarize_document import SummarizeDocumentUseCase
from app.application.use_cases.assistant.helpers import append_message, derive_title
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.core.config import settings
from app.domain.entities.object import UniversalObject
from app.domain.repositories.vector_repository import VectorRepository
from app.domain.value_objects.enums import ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.session import get_db
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.persistence.annotation_store import SQLAnnotationStore
from app.infrastructure.persistence.claim_store import SQLClaimStore
from app.infrastructure.persistence.document_content_store import SQLDocumentContentStore
from app.infrastructure.persistence.document_chunk_store import SQLDocumentChunkStore
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.repositories.sqlalchemy_search_repository import (
    SQLAlchemySearchRepository,
)
from app.infrastructure.search.index_applier import SearchIndexApplier

router = APIRouter(prefix="/ai", tags=["AI"])


class AiHealthResponseModel(BaseModel):
    """Aggregate AI health (GET /ai/health)."""

    status: str
    ai_enabled: bool
    default_provider: str
    default_model: str
    default_provider_valid: bool
    providers_total: int
    providers_configured: int
    feature_flags: dict[str, bool]
    checked_at: str


class AiModelResponseModel(BaseModel):
    """One model in the aggregated catalogue.

    ``protected_namespaces=()``: the ``model_id`` field is a legitimate
    contract name, not a pydantic ``model_*`` namespace collision.
    """

    model_config = ConfigDict(protected_namespaces=())

    provider_id: str
    model_id: str
    display_name: str = ""
    context_window: int | None = None
    capabilities: list[str] = Field(default_factory=list)
    configured: bool


class AiProviderResponseModel(BaseModel):
    """One provider row (GET /ai/providers)."""

    provider_id: str
    display_name: str
    kind: str
    status: str
    configured: bool
    executable: bool = False
    operational: bool | None = None
    models: list[AiModelResponseModel] = Field(default_factory=list)
    detail: str = ""


class ListAiProvidersResponseModel(BaseModel):
    items: list[AiProviderResponseModel]


class AiModelsResponseModel(BaseModel):
    default_provider: str
    default_model: str
    models: list[AiModelResponseModel]


@router.get("/health", response_model=AiHealthResponseModel)
def ai_health(
    core: AiCore = Depends(get_ai_core),
) -> AiHealthResponseModel:
    """Aggregate AI health. Public (liveness probe), JSON only.

    ``status`` is one of ``ok`` | ``not_configured`` | ``disabled`` |
    ``error``; M11.1 reports ``not_configured`` (no adapter is wired).
    """
    summary = GetAiHealthUseCase(core).execute()
    return AiHealthResponseModel(**health_summary_dict(summary))


@router.get("/providers", response_model=ListAiProvidersResponseModel)
def list_ai_providers(
    core: AiCore = Depends(get_ai_core),
    user=Depends(get_current_user),
) -> ListAiProvidersResponseModel:
    """The provider catalogue: status + configured models per provider.

    Configuration-derived, so this endpoint requires authentication.
    """
    del user  # auth gate only
    records = ListAiProvidersUseCase(core).execute()
    return ListAiProvidersResponseModel(
        items=[AiProviderResponseModel(**provider_record_dict(r)) for r in records]
    )


@router.get("/models", response_model=AiModelsResponseModel)
def list_ai_models(
    core: AiCore = Depends(get_ai_core),
    user=Depends(get_current_user),
) -> AiModelsResponseModel:
    """The aggregated model catalogue plus the configured defaults.

    Configuration-derived, so this endpoint requires authentication.
    """
    del user  # auth gate only
    summary = ListAiModelsUseCase(core).execute()
    return AiModelsResponseModel(**models_summary_dict(summary))


class SummarizeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_id: str


class SummarizeResponseModel(BaseModel):
    """Document summary result (POST /ai/summarize)."""

    summary: str
    available: bool
    truncated: bool = False
    chars_used: int = 0
    chars_total: int = 0
    # Provenance contract (M13.1; retrofitted in M13.3).
    provider_id: str = ""
    model: str = ""
    prompt_id: str = ""
    prompt_version: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    token_usage_estimated: bool = True
    latency_ms: int = 0


@router.post("/summarize", response_model=SummarizeResponseModel)
def summarize_document(
    body: SummarizeBody,
    core: AiCore = Depends(get_ai_core),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
):
    """Generate an on-demand summary of a document (M12.1).

    Feature-flagged (``AI_SUMMARIZATION_ENABLED``). Requires authentication
    and READ permission on the document. Returns a summary with truncation
    disclosure and an honest fallback when the gateway is unavailable.
    """
    # Configuration authority: the AI Core config is the single source of truth.
    # When AI_ENABLED is false (the master switch) NO AI capability may invoke
    # generate() — including summarization. The summarization feature flag is
    # checked via the same config view, not a second source.
    if not core.config.enabled or not core.config.feature_flags.get("summarization", False):
        raise HTTPException(status_code=404)

    repo = SQLAlchemyObjectRepository(db)
    annotation_service = DocumentAnnotationService(repo, SQLAnnotationStore(db), content_store=SQLDocumentContentStore(db))
    evaluator = ObjectPermissionEvaluator()
    use_case = SummarizeDocumentUseCase(repo, annotation_service, evaluator, core)
    try:
        result = use_case.execute(body.object_id, user, storage)
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SummarizeResponseModel(**summarize_result_dict(result))



class EnrichBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_id: str


class EnrichmentResponseModel(BaseModel):
    """Document enrichment result (POST /ai/enrich)."""

    title: str = ""
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    available: bool
    truncated: bool = False
    chars_used: int = 0
    chars_total: int = 0
    provider_id: str = ""
    model: str = ""
    prompt_id: str = ""
    prompt_version: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    token_usage_estimated: bool = True
    latency_ms: int = 0
    persisted: bool = False


@router.post("/enrich", response_model=EnrichmentResponseModel)
def enrich_document(
    body: EnrichBody,
    core: AiCore = Depends(get_ai_core),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
):
    """Extract structured enrichment metadata from a document (M13.2).

    The first production use of ``structured_generate``: returns title,
    summary, tags, categories and keywords derived from the document's
    authoritative text, with provenance. Feature-flagged
    (``AI_ENRICHMENT_ENABLED``). Requires authentication and READ permission.
    """
    # Configuration authority: the AI Core config is the single source of truth.
    if not core.config.enabled or not core.config.feature_flags.get("enrichment", False):
        raise HTTPException(status_code=404)

    repo = SQLAlchemyObjectRepository(db)
    annotation_service = DocumentAnnotationService(repo, SQLAnnotationStore(db), content_store=SQLDocumentContentStore(db))
    evaluator = ObjectPermissionEvaluator()
    use_case = EnrichDocumentUseCase(repo, annotation_service, evaluator, core)
    try:
        result = use_case.execute(body.object_id, user, storage)
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return EnrichmentResponseModel(**enrichment_result_dict(result))



class QABody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str


class QACitationModel(BaseModel):
    number: int
    object_id: str
    object_type: str
    title: str


class QAResponseModel(BaseModel):
    """Grounded QA result (POST /ai/qa)."""

    answer: str
    available: bool
    retrieved_count: int = 0
    truncated: bool = False
    citations: list[dict] = Field(default_factory=list)
    provider_id: str = ""
    model: str = ""
    prompt_id: str = ""
    prompt_version: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    token_usage_estimated: bool = True
    latency_ms: int = 0
    # V3 M5 — answering-ladder contract (blueprint §M5). Optional/defaulted so
    # existing clients are unaffected. rung=0 means a confirmed-claims answer
    # (source_class="claims", cost 0, no model). LLM answers report rung=None.
    rung: int | None = None
    source_class: str = ""
    cost: float = 0.0
    evidence: list[dict] = Field(default_factory=list)


def _qa_retrieval(
    db: Session,
    repo: SQLAlchemyObjectRepository,
    vector_repository: VectorRepository | None,
    embedder: Embedder,
) -> AssistantRetrievalService:
    """Construct the retrieval service (reused Assistant infrastructure).

    Read-time repair (M16): drain pending outbox events first so retrieval
    sees current documents — the same contract as ``GET /search`` (M14.1).
    Without this, freshly created objects are invisible to QA/chat/handoff
    until a separate search drains the index. Best-effort: a drain failure
    must never block retrieval.
    """
    try:
        SearchIndexApplier(
            db, vector_repository=vector_repository, embedder=embedder
        ).apply_pending()
        db.commit()
    except Exception:  # noqa: BLE001 — retrieval must never fail on repair
        db.rollback()
    search = SearchObjectsUseCase(
        search_repository=SQLAlchemySearchRepository(db),
        object_repository=repo,
        permission_evaluator=ObjectPermissionEvaluator(),
        vector_repository=vector_repository,
        embedder=embedder,
    )
    graph = GraphRuntimeService(repo, ObjectPermissionEvaluator())
    # P0-2: the repository enriches graph-only retrieval items with their
    # metadata so the LLM receives evidence beyond titles.
    return AssistantRetrievalService(search, graph, repository=repo)


def _sse(event: str, data: dict) -> str:
    """One Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/qa", response_model=QAResponseModel)
def grounded_qa(
    body: QABody,
    core: AiCore = Depends(get_ai_core),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
):
    """Grounded question answering (M13.1).

    Retrieves relevant documents (permission-filtered), generates a grounded
    answer with verified citations, and returns provenance metadata.
    Feature-flagged (``AI_QA_ENABLED``).
    """
    if not core.config.enabled or not core.config.feature_flags.get("qa", False):
        raise HTTPException(status_code=404)

    # V3 M5 rung-0: answer from CONFIRMED claims before any retrieval or LLM
    # (blueprint §B1 answering ladder, §M5 fast path). Deterministic and free;
    # a miss simply falls through to the grounded pipeline. Feature-flagged
    # (ai_rung0_enabled) for rollback; no LLM is ever invoked here.
    if settings.ai_rung0_enabled:
        rung0 = Rung0ClaimAnswerer(SQLClaimStore(db)).answer(body.question, str(user.id))
        if rung0 is not None:
            return QAResponseModel(
                answer=rung0.value,
                available=True,
                retrieved_count=0,
                citations=[],
                rung=rung0.rung,
                source_class=rung0.source_class,
                cost=0.0,
                evidence=rung0.to_dict()["evidence"],
            )

    # M13.3.1 full-system audit: resolve the embedder/vector AFTER the gate
    # (the same get_embedder/get_vector_repository functions /search uses) so a
    # disabled QA feature never resolves the AI embedder nor touches the
    # vector store.
    embedder = get_embedder(core)
    vector_repository = get_vector_repository(embedder)

    repo = SQLAlchemyObjectRepository(db)
    retrieval = _qa_retrieval(db, repo, vector_repository, embedder)
    use_case = GroundedQAUseCase(
        repo, retrieval, core,
        citation_builder=CitationBuilder(),
        verifier=AnswerVerifier(ObjectPermissionEvaluator()),
        annotation_service=DocumentAnnotationService(repo, SQLAnnotationStore(db), content_store=SQLDocumentContentStore(db)),
        chunk_store=SQLDocumentChunkStore(db),
        storage=storage,
        max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
    )
    result = use_case.execute(body.question, user)
    return QAResponseModel(**qa_result_dict(result))


@router.post("/qa/stream")
def grounded_qa_stream(
    body: QABody,
    core: AiCore = Depends(get_ai_core),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
):
    """Streaming grounded QA (M13.1): SSE over the same pipeline as ``POST /ai/qa``.

    Events: ``token`` (partial deltas, flushed only on confirmed success),
    ``completion`` (verified answer + provenance). Feature-flagged
    (``AI_QA_ENABLED``).
    """
    if not core.config.enabled or not core.config.feature_flags.get("qa", False):
        raise HTTPException(status_code=404)

    # M13.3.1 full-system audit: resolve the embedder/vector AFTER the gate
    # (the same get_embedder/get_vector_repository functions /search uses) so a
    # disabled QA feature never resolves the AI embedder nor touches the
    # vector store.
    embedder = get_embedder(core)
    vector_repository = get_vector_repository(embedder)

    repo = SQLAlchemyObjectRepository(db)
    retrieval = _qa_retrieval(db, repo, vector_repository, embedder)
    use_case = GroundedQAUseCase(
        repo, retrieval, core,
        citation_builder=CitationBuilder(),
        verifier=AnswerVerifier(ObjectPermissionEvaluator()),
        annotation_service=DocumentAnnotationService(repo, SQLAnnotationStore(db), content_store=SQLDocumentContentStore(db)),
        chunk_store=SQLDocumentChunkStore(db),
        storage=storage,
        max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
    )

    def events():
        for event in use_case.stream(body.question, user):
            if event["type"] == "token":
                yield _sse("token", {"delta": event["delta"]})
            elif event["type"] == "complete":
                yield _sse("completion", qa_result_dict(event["result"]))

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )



class RelatedDocumentItemModel(BaseModel):
    """One related document (GET /ai/related)."""

    object_id: str
    object_type: str
    title: str
    score: float
    version: int = 0


class RelatedDocumentsResponseModel(BaseModel):
    """Related documents result (GET /ai/related)."""

    items: list[RelatedDocumentItemModel] = Field(default_factory=list)


@router.get("/related", response_model=RelatedDocumentsResponseModel)
def related_documents(
    object_id: str = Query(..., description="The source document/object id."),
    limit: int = Query(10, ge=1, le=50),
    core: AiCore = Depends(get_ai_core),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
):
    """Documents semantically related to a source (M13.3).

    Reuses the existing embedding/vector-search infrastructure (the SAME
    resolved embedder and vector repository as semantic search). READ
    permission on the source is enforced before its text is embedded; every
    result is re-authorized against the authoritative object, and the source
    is never returned. Feature-flagged (``AI_RELATED_DOCUMENTS_ENABLED``).

    M13.3.1 (defect-1 fix): the feature gate runs BEFORE the embedder/vector
    infrastructure is resolved. The embedder and vector repository are resolved
    inline (after the gate) via the SAME functions ``/search`` uses, so a
    disabled feature never resolves the AI embedder nor touches the
    Qdrant/vector store.
    """
    # Configuration authority: the AI Core config is the single source of truth.
    # Checked FIRST — before any embedder/vector resolution — so a disabled
    # feature never resolves the AI embedder or queries the vector store.
    if not core.config.enabled or not core.config.feature_flags.get("related_documents", False):
        raise HTTPException(status_code=404)

    # Resolved inline AFTER the gate (the same functions /search uses).
    embedder = get_embedder(core)
    vector_repository = get_vector_repository(embedder)

    repo = SQLAlchemyObjectRepository(db)
    annotation_service = DocumentAnnotationService(repo, SQLAnnotationStore(db), content_store=SQLDocumentContentStore(db))
    evaluator = ObjectPermissionEvaluator()
    use_case = RelatedDocumentsUseCase(
        repo, annotation_service, evaluator, vector_repository, embedder,
    )
    try:
        result = use_case.execute(object_id, user, storage, limit=limit)
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RelatedDocumentsResponseModel(**related_documents_result_dict(result))


class ChatMessageModel(BaseModel):
    """One prior conversation turn supplied by the client (stateless chat)."""

    model_config = ConfigDict(extra="forbid")

    role: str
    content: str


class ChatBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    history: list[ChatMessageModel] = Field(default_factory=list)
    conversation_id: str | None = None


class ChatResponseModel(BaseModel):
    """Conversational, document-grounded chat result (POST /ai/chat)."""

    answer: str
    available: bool
    retrieved_count: int = 0
    truncated: bool = False
    citations: list[dict] = Field(default_factory=list)
    provider_id: str = ""
    model: str = ""
    prompt_id: str = ""
    prompt_version: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    token_usage_estimated: bool = True
    latency_ms: int = 0
    conversation_id: str | None = None
    confidence: str = ""


def _build_chat_use_case(core, db, repo, storage):
    """Compose the chat use case over the shared grounded-generation engine,
    reusing the QA retrieval + citation/verification/grounding wiring but with
    chat-specific system instructions."""
    embedder = get_embedder(core)
    vector_repository = get_vector_repository(embedder)
    retrieval = _qa_retrieval(db, repo, vector_repository, embedder)
    grounded = GroundedQAUseCase(
        repo, retrieval, core,
        prompt_builder=AssistantPromptBuilder(system_instructions=CHAT_SYSTEM_INSTRUCTIONS),
        citation_builder=CitationBuilder(),
        verifier=AnswerVerifier(ObjectPermissionEvaluator()),
        annotation_service=DocumentAnnotationService(repo, SQLAnnotationStore(db), content_store=SQLDocumentContentStore(db)),
        chunk_store=SQLDocumentChunkStore(db),
        storage=storage,
        max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
    )
    return ChatUseCase(grounded)


@router.post("/chat", response_model=ChatResponseModel)
def ai_chat(
    body: ChatBody,
    core: AiCore = Depends(get_ai_core),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
):
    """Conversational document-grounded chat (M15 — F17).

    Grounds the latest message in the caller's readable documents, carrying the
    supplied conversation history for coherent multi-turn chat. Stateless
    (server keeps no conversation); feature-flagged (``AI_CHAT_ENABLED``).
    """
    # Configuration authority — checked BEFORE resolving embedder/vector so a
    # disabled feature never touches the AI embedder nor the vector store.
    if not core.config.enabled or not core.config.feature_flags.get("chat", False):
        raise HTTPException(status_code=404)

    repo = SQLAlchemyObjectRepository(db)
    use_case = _build_chat_use_case(core, db, repo, storage)

    # M19: server-side conversation persistence.
    conversation = None
    if body.conversation_id:
        conv_obj = repo.get_by_id(ObjectId(body.conversation_id))
        if conv_obj is not None and conv_obj.object_type == ObjectType.AI_CONVERSATION:
            conversation = conv_obj
    elif not body.history:
        # First turn of a new persistent conversation (no client history).
        from app.domain.value_objects.enums import ObjectType as _OT
        conversation = UniversalObject.create(
            _OT.AI_CONVERSATION,
            derive_title(body.message),
            created_by=str(user.id),
            object_id=ObjectId.generate(_OT.AI_CONVERSATION),
        )

    history = [ChatTurn(turn.role, turn.content) for turn in body.history]
    result = use_case.execute(body.message, history, user, conversation=conversation)

    # Persist user + assistant messages on the conversation.
    if conversation is not None:
        append_message(conversation, "user", body.message, answer=None)
        if result.available:
            append_message(conversation, "assistant", result.answer, answer=None)
        events = conversation.pop_domain_events()
        outbox_rows = [to_outbox_row(e) for e in events]
        repo.save(conversation, outbox_events=outbox_rows)

    response_data = qa_result_dict(result)
    response_data["conversation_id"] = (
        str(conversation.id) if conversation is not None else None
    )
    return ChatResponseModel(**response_data)


@router.post("/chat/stream")
def ai_chat_stream(
    body: ChatBody,
    core: AiCore = Depends(get_ai_core),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
):
    """Streaming chat (M15): SSE over the same grounded pipeline as ``POST /ai/chat``.

    Events: ``token`` (partial deltas, flushed only on confirmed success),
    ``completion`` (verified answer + provenance + ``conversation_id`` when a
    conversation is active). Feature-flagged (``AI_CHAT_ENABLED``). Inherits
    the leak-proof streaming contract.

    Reconciliation pass — M19 parity with the synchronous endpoint: the same
    server-side conversation persistence (create/lookup on ``conversation_id``,
    append user + assistant messages, outbox rows in the same transaction).
    Without it, the streaming path — now the primary UI path — silently lost
    conversation history. The persistence happens after the final event so it
    never delays a single token.
    """
    # Configuration authority — checked BEFORE resolving embedder/vector so a
    # disabled feature never touches the AI embedder nor the vector store.
    if not core.config.enabled or not core.config.feature_flags.get("chat", False):
        raise HTTPException(status_code=404)

    repo = SQLAlchemyObjectRepository(db)
    use_case = _build_chat_use_case(core, db, repo, storage)

    # M19: server-side conversation persistence (mirrors POST /ai/chat).
    conversation = None
    if body.conversation_id:
        conv_obj = repo.get_by_id(ObjectId(body.conversation_id))
        if conv_obj is not None and conv_obj.object_type == ObjectType.AI_CONVERSATION:
            conversation = conv_obj
    elif not body.history:
        # First turn of a new persistent conversation (no client history).
        from app.domain.value_objects.enums import ObjectType as _OT
        conversation = UniversalObject.create(
            _OT.AI_CONVERSATION,
            derive_title(body.message),
            created_by=str(user.id),
            object_id=ObjectId.generate(_OT.AI_CONVERSATION),
        )

    history = [ChatTurn(turn.role, turn.content) for turn in body.history]
    # Track the final answer so the conversation row is written once the
    # stream completes (never before the verified answer exists).
    final = {"text": None, "available": False}

    def events():
        for event in use_case.stream(body.message, history, user, conversation=conversation):
            if event["type"] == "token":
                yield _sse("token", {"delta": event["delta"]})
            elif event["type"] == "complete":
                result = event["result"]
                final["text"] = result.answer if result.available else None
                final["available"] = result.available
                data = qa_result_dict(result)
                if conversation is not None:
                    data["conversation_id"] = str(conversation.id)
                yield _sse("completion", data)
        # Persist after the stream ends — never before the first token.
        if conversation is not None:
            try:
                append_message(conversation, "user", body.message, answer=None)
                if final["available"] and final["text"]:
                    append_message(conversation, "assistant", final["text"], answer=None)
                events_out = conversation.pop_domain_events()
                repo.save(conversation, outbox_events=[to_outbox_row(e) for e in events_out])
                db.commit()
            except Exception:  # noqa: BLE001 — persistence must never break a stream
                db.rollback()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

class AssistantRoleModel(BaseModel):
    """One domain-assistant role in the catalogue (GET /ai/assistants)."""

    key: str
    display_name: str
    description: str


class ListAssistantRolesResponseModel(BaseModel):
    """The domain-assistant catalogue (GET /ai/assistants)."""

    items: list[AssistantRoleModel]


class AssistantBody(BaseModel):
    """One domain-assistant request (POST /ai/assistants/{role}).

    Stateless: the caller supplies optional prior turns; the server keeps no
    conversation (the same M15 stateless contract chat started with).
    """

    model_config = ConfigDict(extra="forbid")

    message: str
    history: list[ChatMessageModel] = Field(default_factory=list)


class AssistantResponseModel(BaseModel):
    """Domain-assistant grounded result (POST /ai/assistants/{role})."""

    role: str
    answer: str
    available: bool
    retrieved_count: int = 0
    truncated: bool = False
    citations: list[dict] = Field(default_factory=list)
    provider_id: str = ""
    model: str = ""
    prompt_id: str = ""
    prompt_version: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    token_usage_estimated: bool = True
    latency_ms: int = 0
    confidence: str = ""


def _build_assistant_use_case(core, db, repo, storage, role: DomainAssistantRole):
    """Compose a domain assistant over the shared grounded-generation engine,
    reusing the QA retrieval + citation/verification/grounding wiring but with
    the role-specific system instructions (identical structure to chat)."""
    embedder = get_embedder(core)
    vector_repository = get_vector_repository(embedder)
    retrieval = _qa_retrieval(db, repo, vector_repository, embedder)
    # Domain assistants often draft (lesson plans, replies, sections) —
    # a moderate budget above the factual QA default, still far below the
    # old 1024 cap.
    drafting_budget = 768
    grounded = GroundedQAUseCase(
        repo, retrieval, core,
        prompt_builder=AssistantPromptBuilder(
            system_instructions=role.system_instructions
        ),
        citation_builder=CitationBuilder(),
        verifier=AnswerVerifier(ObjectPermissionEvaluator()),
        annotation_service=DocumentAnnotationService(repo, SQLAnnotationStore(db), content_store=SQLDocumentContentStore(db)),
        chunk_store=SQLDocumentChunkStore(db),
        storage=storage,
        max_output_tokens=drafting_budget,
    )
    return DomainAssistantUseCase(grounded, role)


@router.get("/assistants", response_model=ListAssistantRolesResponseModel)
def list_assistant_roles(
    core: AiCore = Depends(get_ai_core),
    user=Depends(get_current_user),
) -> ListAssistantRolesResponseModel:
    """The domain-assistant catalogue (Group D, F18-F21).

    Configuration-derived (the role catalogue is static), so it requires
    authentication. Returns every role regardless of the feature flag so the
    UI can label the layer as available-but-disabled when the flag is off.
    """
    del core, user  # auth gate only
    return ListAssistantRolesResponseModel(
        items=[
            AssistantRoleModel(
                key=r.key, display_name=r.display_name, description=r.description
            )
            for r in ASSISTANT_ROLES.values()
        ]
    )


@router.post("/assistants/{role}", response_model=AssistantResponseModel)
def ai_assistant(
    role: str,
    body: AssistantBody,
    core: AiCore = Depends(get_ai_core),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
):
    """Domain-assistant grounded generation (M22-M25 - F18-F21).

    Role-specialized grounded generation over the caller's readable documents.
    The teaching role applies the academic-integrity guard before generation
    (refuses assessable-completion requests, scaffolds instead). Feature-flagged
    (``AI_ASSISTANTS_ENABLED``).
    """
    if not core.config.enabled or not core.config.feature_flags.get("assistants", False):
        raise HTTPException(status_code=404)
    if role not in ASSISTANT_ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown assistant role: {role!r}. Expected one of {list(ASSISTANT_ROLE_KEYS)}.",
        )
    repo = SQLAlchemyObjectRepository(db)
    use_case = _build_assistant_use_case(core, db, repo, storage, ASSISTANT_ROLES[role])
    history = [ChatTurn(turn.role, turn.content) for turn in body.history]
    result = use_case.execute(body.message, history, user)
    return AssistantResponseModel(**domain_assistant_result_dict(result, role))


@router.post("/assistants/{role}/stream")
def ai_assistant_stream(
    role: str,
    body: AssistantBody,
    core: AiCore = Depends(get_ai_core),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
):
    """Streaming domain-assistant generation (M22-M25): SSE over the same
    grounded pipeline as ``POST /ai/assistants/{role}``.

    Events: ``token`` (partial deltas), ``completion`` (answer + provenance).
    The teaching integrity refusal is yielded as a single ``completion``.
    Feature-flagged (``AI_ASSISTANTS_ENABLED``).
    """
    if not core.config.enabled or not core.config.feature_flags.get("assistants", False):
        raise HTTPException(status_code=404)
    if role not in ASSISTANT_ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown assistant role: {role!r}. Expected one of {list(ASSISTANT_ROLE_KEYS)}.",
        )
    repo = SQLAlchemyObjectRepository(db)
    use_case = _build_assistant_use_case(core, db, repo, storage, ASSISTANT_ROLES[role])
    history = [ChatTurn(turn.role, turn.content) for turn in body.history]

    def events():
        for event in use_case.stream(body.message, history, user):
            if event["type"] == "token":
                yield _sse("token", {"delta": event["delta"]})
            elif event["type"] == "complete":
                yield _sse("completion", domain_assistant_result_dict(event["result"], role))

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class HandoffBody(BaseModel):
    """External-AI handoff request (POST /ai/handoff)."""

    model_config = ConfigDict(extra="forbid")

    task: str = "qa"
    question: str


class HandoffSourceModel(BaseModel):
    number: int
    object_id: str
    object_type: str
    title: str


class HandoffResponseModel(BaseModel):
    """A copyable grounded prompt bundle for an external AI (POST /ai/handoff)."""

    task: str
    system_prompt: str
    user_prompt: str
    combined_prompt: str
    sources: list[HandoffSourceModel] = Field(default_factory=list)
    source_count: int = 0
    truncated: bool = False
    expected_format: str = ""
    instructions: str = ""
    note: str = ""


@router.post("/handoff", response_model=HandoffResponseModel)
def ai_handoff(
    body: HandoffBody,
    core: AiCore = Depends(get_ai_core),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
):
    """External-AI handoff (M16) — the no-provider / no-cost path.

    Builds a self-contained, grounded prompt bundle the caller can paste into
    any external AI. NO gateway is invoked (no key, no charge). The prompt is
    grounded in the caller's readable documents exactly like grounded QA.

    Deliberately NOT gated on ``AI_ENABLED``: the handoff is the free fallback
    for environments with no AI provider — its purpose is to work *without* AI.
    Authentication and READ permission still apply (retrieval is permission
    filtered; with AI off it degrades to lexical search).
    """
    task = (body.task or "qa").strip()
    if task not in SUPPORTED_TASKS:
        raise HTTPException(status_code=422, detail=f"Unsupported task: {task!r}")
    if not (body.question or "").strip():
        raise HTTPException(status_code=422, detail="A non-empty question is required.")

    repo = SQLAlchemyObjectRepository(db)
    # Retrieval uses the resolved embedder/vector (lexical HashingEmbedder
    # fallback when AI is off); NO gateway is constructed or called.
    embedder = get_embedder(core)
    vector_repository = get_vector_repository(embedder)
    retrieval = _qa_retrieval(db, repo, vector_repository, embedder)
    grounded = GroundedQAUseCase(
        repo, retrieval, core,
        citation_builder=CitationBuilder(),
        annotation_service=DocumentAnnotationService(repo, SQLAnnotationStore(db), content_store=SQLDocumentContentStore(db)),
        chunk_store=SQLDocumentChunkStore(db),
        storage=storage,
    )
    use_case = HandoffUseCase(grounded)
    bundle = use_case.execute(task, body.question, user)
    return HandoffResponseModel(**handoff_bundle_dict(bundle))

__all__ = [
    "AiHealthResponseModel",
    "AiModelResponseModel",
    "AiModelsResponseModel",
    "AiProviderResponseModel",
    "ListAiProvidersResponseModel",
    "SummarizeBody",
    "SummarizeResponseModel",
    "EnrichBody",
    "EnrichmentResponseModel",
    "RelatedDocumentItemModel",
    "RelatedDocumentsResponseModel",
    "QABody",
    "QAResponseModel",
    "ChatBody",
    "ChatResponseModel",
    "AssistantRoleModel",
    "ListAssistantRolesResponseModel",
    "AssistantBody",
    "AssistantResponseModel",
    "HandoffBody",
    "HandoffResponseModel",
    "router",
]
