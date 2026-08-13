"""Search API routes (Sprint-5 M1 foundation + M2 hybrid).

- ``GET  /search`` — hybrid lexical + semantic search over the persistent
  projections. Lexical criteria (exact object type, exact case-insensitive
  title, literal-substring full text) are fused with semantic
  nearest-neighbour results via deterministic reciprocal rank fusion.
  Every result is permission pre-filtered through the R4 evaluator and
  carries provenance (``index_source``: lexical / semantic / both) plus a
  deterministic ``score``. When the semantic layer is unavailable the API
  behaves exactly like Sprint-5 M1 (pure lexical).
- ``POST /search/index/sync`` — drain the durable outbox into the lexical
  AND semantic projections (idempotent; the relay is the only writer).

The indexes never become the source of truth: they are derived
projections, rebuilt from version snapshots, and every search result is
authorized against the authoritative object before it is returned.
"""
from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.ai import get_ai_core
from app.api.dependencies.auth import get_current_user
from app.api.dependencies.db import get_db
from app.application.ai.core import AiCore
from app.api.routes.documents import get_storage as get_documents_storage
from app.application.exceptions import ValidationError
from app.application.ports.embedder import Embedder
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.vector_repository import VectorRepository
from app.infrastructure.embedding.hashing_embedder import HashingEmbedder
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.repositories.sqlalchemy_search_repository import (
    SQLAlchemySearchRepository,
)
from app.infrastructure.search.index_applier import SearchIndexApplier
from app.infrastructure.search.document_content_rebuilder import rebuild_document_contents
from app.infrastructure.vector_db.client import get_qdrant_client
from app.infrastructure.vector_db.collections import VectorCollectionManager
from app.infrastructure.vector_db.qdrant_vector_repository import (
    QdrantVectorRepository,
)

_log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/search",
    tags=["search"],
    dependencies=[Depends(get_current_user)],
)


class SearchHitModel(BaseModel):
    object_id: str
    object_type: str
    title: str
    version: int
    # Sprint-5 M2 provenance: which index leg produced the hit.
    index_source: str
    score: float  # deterministic reciprocal-rank-fusion score


class SearchResponseModel(BaseModel):
    results: list[SearchHitModel]


class IndexSyncResponseModel(BaseModel):
    applied: int


def get_embedder(ai_core: AiCore = Depends(get_ai_core)) -> Embedder:
    """Resolve the active embedder (M12.3).

    When ``AI_SEMANTIC_SEARCH_ENABLED`` is on, the AI Core's embedder is used
    (real OpenAI embeddings or the configured model). When off (or when the
    AI Core has no embedding provider), the deterministic ``HashingEmbedder``
    fallback is used - identical to pre-M12 behavior.
    """
    # Configuration authority (M12.3.1): the AI Core config is the single
    # source of truth. When AI_ENABLED is false (master switch) no AI
    # capability may resolve — including the embedder. The semantic-search
    # feature flag is checked via the same config view, not a second source.
    if not ai_core.config.enabled or not ai_core.config.feature_flags.get("semantic_search", False):
        return HashingEmbedder()
    try:
        return ai_core.embedder()
    except Exception:  # noqa: BLE001 - semantic must never break search
        _log.warning(
            "AI Core embedder unavailable; falling back to HashingEmbedder.",
            exc_info=True,
        )
        return HashingEmbedder()


# The semantic stack is a process-lifetime lazy singleton: one client, one
# ensured collection, shared by every request. For the in-process Qdrant
# emulator (``:memory:``) this is REQUIRED — its state lives in the client
# instance; for a real server it removes per-request provisioning RPCs.
# Failures are not cached, so a later request retries the build.
_semantic_lock = threading.Lock()
_semantic_repository: VectorRepository | None = None
_semantic_repository_ready = False


def get_vector_repository(
    embedder: Embedder = Depends(get_embedder),
) -> VectorRepository | None:
    """The semantic index adapter, or ``None`` when unavailable.

    Graceful degradation seam: any failure (Qdrant unreachable or
    misconfigured) yields ``None`` and the search stack falls back to the
    M1 lexical contract. Overridable in tests via dependency_overrides.
    """
    global _semantic_repository, _semantic_repository_ready
    if _semantic_repository_ready:
        return _semantic_repository
    with _semantic_lock:
        if _semantic_repository_ready:
            return _semantic_repository
        try:
            client = get_qdrant_client()
            collection = VectorCollectionManager(
                client, dimensions=embedder.dimensions
            ).ensure()
            _semantic_repository = QdrantVectorRepository(client, collection)
            _semantic_repository_ready = True
        except Exception:  # noqa: BLE001 — semantic must never break search
            _log.warning(
                "Semantic search unavailable; lexical-only fallback.", exc_info=True
            )
    return _semantic_repository


def _search_use_case(
    db: Session,
    vector_repository: VectorRepository | None,
    embedder: Embedder,
) -> SearchObjectsUseCase:
    return SearchObjectsUseCase(
        search_repository=SQLAlchemySearchRepository(db),
        object_repository=SQLAlchemyObjectRepository(db),
        permission_evaluator=ObjectPermissionEvaluator(),
        vector_repository=vector_repository,
        embedder=embedder,
    )


@router.get("", response_model=SearchResponseModel)
def search_objects(
    text: str | None = Query(None, max_length=200),
    object_type: str | None = Query(None, max_length=64),
    title: str | None = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
    vector_repository: VectorRepository | None = Depends(get_vector_repository),
    embedder: Embedder = Depends(get_embedder),
) -> SearchResponseModel:
    # M14.1 read-time repair: drain pending outbox events into the derived
    # search projection BEFORE querying, so it reflects all committed writes.
    # The system ships no always-on outbox relay; without this, newly created
    # objects are invisible to search until a manual ``/search/index/sync``.
    # Idempotent and bounded (drains only pending events); best-effort — a
    # drain failure must never break search.
    try:
        SearchIndexApplier(
            db, vector_repository=vector_repository, embedder=embedder
        ).apply_pending()
        db.commit()
    except Exception:  # noqa: BLE001 — search must never fail because of repair
        db.rollback()
    try:
        hits = _search_use_case(db, vector_repository, embedder).execute(
            user=user,
            text=text,
            object_type=object_type,
            title=title,
            limit=limit,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return SearchResponseModel(
        results=[
            SearchHitModel(
                object_id=hit.object_id,
                object_type=hit.object_type,
                title=hit.title,
                version=hit.version,
                index_source=hit.index_source,
                score=hit.score,
            )
            for hit in hits
        ]
    )


@router.post("/index/sync", response_model=IndexSyncResponseModel)
def sync_search_index(
    db: Session = Depends(get_db),
    vector_repository: VectorRepository | None = Depends(get_vector_repository),
    embedder: Embedder = Depends(get_embedder),
) -> IndexSyncResponseModel:
    return IndexSyncResponseModel(
        **SearchIndexApplier(
            db, vector_repository=vector_repository, embedder=embedder
        ).apply_pending()
    )


class ContentRebuildResponseModel(BaseModel):
    """Result of the document-content + chunk projection rebuild (M27+P0)."""

    indexed: int
    skipped: int
    chunked: int = 0


@router.post("/content/rebuild", response_model=ContentRebuildResponseModel)
def rebuild_document_content(
    db: Session = Depends(get_db),
    storage=Depends(get_documents_storage),
) -> ContentRebuildResponseModel:
    """Rebuild the document-content search projection from durable state
    (M27): every DOCUMENT's linked intake item's extracted-text blob. Derived
    data only — the blobs remain authoritative; idempotent; runs in one
    transaction. Skipped documents (no intake item / no extracted text) stay
    searchable by title/metadata."""
    result = rebuild_document_contents(db, storage)
    return ContentRebuildResponseModel(**result)
