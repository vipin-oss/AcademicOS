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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.mappers.assistant_mapper import (
    output_dict,
    to_ask_input,
    to_create_input,
    to_delete_input,
    to_update_input,
)
from app.api.routes.search import get_embedder, get_vector_repository
from app.application.assistant.context_builder import AssistantContextBuilder
from app.application.assistant.providers import RuleBasedAssistantProvider
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
from app.application.services.assistant_retrieval import AssistantRetrievalService
from app.application.services.graph_runtime import GraphRuntimeService
from app.application.use_cases.assistant.ask_question import AskQuestionUseCase
from app.application.use_cases.assistant.create_conversation import CreateConversationUseCase
from app.application.use_cases.assistant.delete_conversation import DeleteConversationUseCase
from app.application.use_cases.assistant.get_conversation import GetConversationUseCase
from app.application.use_cases.assistant.get_home import GetAssistantHomeUseCase
from app.application.use_cases.assistant.list_conversations import ListConversationsUseCase
from app.application.use_cases.assistant.update_conversation import UpdateConversationUseCase
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.vector_repository import VectorRepository
from app.infrastructure.db.session import get_db
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
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
    """Composition seam: V1 = local rules; future sanctioned LLM adapters plug
    in HERE (integration tests already override this dependency). The rules
    provider is wired with the shared R4 evaluator so its degradation path
    is scoped to the initiator's permissions (S6 M1)."""
    return RuleBasedAssistantProvider(
        repo, permission_evaluator=ObjectPermissionEvaluator()
    )


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
    model_config = ConfigDict(extra="forbid")


class AskBody(StrictBody):
    question: str
    conversation_id: str | None = None
    asked_by: str | None = None


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
    user: UniversalObject = Depends(get_current_user),
):
    try:
        out = AskQuestionUseCase(
            repo,
            provider,
            retrieval=retrieval,
            context_builder=AssistantContextBuilder(),
        ).execute(
            AskQuestionCommand(input=to_ask_input({**body.model_dump(), "asked_by": str(user.id)}))
        )
    except ValidationError as exc:
        raise _unprocessable(exc) from exc
    except ObjectNotFoundError as exc:
        raise _not_found(exc) from exc
    return output_dict(out)


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
