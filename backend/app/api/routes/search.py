"""Search API routes (Sprint-5 M1 — Global Search Foundation).

- ``GET  /search`` — query the persistent search projection. Only the
  roadmap-approved criteria (exact object type, exact case-insensitive
  title, literal-substring full text) with deterministic ordering.
  Results are permission pre-filtered through the R4 evaluator.
- ``POST /search/index/sync`` — drain the durable outbox into the search
  index (idempotent; the index is eventually consistent by design — the
  relay is the only writer, never the object write path).

The index never becomes the source of truth: it is a derived projection,
rebuilt from version snapshots, and every search result is authorized
against the authoritative object before it is returned.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.db import get_db
from app.application.exceptions import ValidationError
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.domain.entities.object import UniversalObject
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.repositories.sqlalchemy_search_repository import (
    SQLAlchemySearchRepository,
)
from app.infrastructure.search.index_applier import SearchIndexApplier

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


class SearchResponseModel(BaseModel):
    results: list[SearchHitModel]


class IndexSyncResponseModel(BaseModel):
    applied: int


def _search_use_case(db: Session) -> SearchObjectsUseCase:
    return SearchObjectsUseCase(
        search_repository=SQLAlchemySearchRepository(db),
        object_repository=SQLAlchemyObjectRepository(db),
        permission_evaluator=ObjectPermissionEvaluator(),
    )


@router.get("", response_model=SearchResponseModel)
def search_objects(
    text: str | None = Query(None, max_length=200),
    object_type: str | None = Query(None, max_length=64),
    title: str | None = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> SearchResponseModel:
    try:
        hits = _search_use_case(db).execute(
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
            )
            for hit in hits
        ]
    )


@router.post("/index/sync", response_model=IndexSyncResponseModel)
def sync_search_index(
    db: Session = Depends(get_db),
) -> IndexSyncResponseModel:
    return IndexSyncResponseModel(**SearchIndexApplier(db).apply_pending())
