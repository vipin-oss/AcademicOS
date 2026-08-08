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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.dependencies.ai import get_ai_core
from app.api.dependencies.auth import get_current_user
from app.api.routes.documents import get_storage
from app.application.ai.core import AiCore
from app.application.dtos.ai import (
    health_summary_dict,
    models_summary_dict,
    provider_record_dict,
    summarize_result_dict,
)
from app.application.exceptions import (
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.application.services.document_annotation_service import (
    DocumentAnnotationService,
)
from app.application.use_cases.ai.get_ai_health import GetAiHealthUseCase
from app.application.use_cases.ai.list_ai_models import ListAiModelsUseCase
from app.application.use_cases.ai.list_ai_providers import ListAiProvidersUseCase
from app.application.use_cases.ai.summarize_document import SummarizeDocumentUseCase
from app.domain.entities.object import UniversalObject
from app.infrastructure.db.session import get_db
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.persistence.annotation_store import SQLAnnotationStore
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

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
    annotation_service = DocumentAnnotationService(repo, SQLAnnotationStore(db))
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



__all__ = [
    "AiHealthResponseModel",
    "AiModelResponseModel",
    "AiModelsResponseModel",
    "AiProviderResponseModel",
    "ListAiProvidersResponseModel",
    "SummarizeBody",
    "SummarizeResponseModel",
    "router",
]
