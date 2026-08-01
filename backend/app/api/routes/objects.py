"""Objects API routes — Phase 1 vertical slice (full CRUD).

Implements the five Object endpoints, all backed by the frozen Application layer:
  - GET    /objects          -> ListObjectsUseCase  (paginated)
  - GET    /objects/{id}     -> GetObjectUseCase
  - POST   /objects          -> CreateObjectUseCase
  - PUT    /objects/{id}     -> UpdateObjectUseCase
  - DELETE /objects/{id}     -> DeleteObjectUseCase

The API depends only on the Application layer (use cases + ports) and on a
repository injected through the session. No domain logic, no new abstractions.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.mappers.object_mapper import to_create_input, to_response, to_update_input
from app.application.commands.create_object import CreateObjectCommand
from app.application.commands.delete_object import DeleteObjectCommand
from app.application.commands.update_object import UpdateObjectCommand
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.queries.get_object import GetObjectQuery
from app.application.queries.list_objects import ListObjectsQuery
from app.application.use_cases.create_object import CreateObjectUseCase
from app.application.use_cases.delete_object import DeleteObjectUseCase
from app.application.use_cases.get_object import GetObjectUseCase
from app.application.use_cases.list_object import ListObjectsUseCase
from app.application.use_cases.update_object import UpdateObjectUseCase
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

router = APIRouter(prefix="/objects", tags=["objects"])


class MetadataField(BaseModel):
    key: str
    value: str
    layer: int = 6
    source: str = "asserted"
    confidence: float | None = None


class CreateObjectRequest(BaseModel):
    object_type: str
    title: str
    created_by: str
    object_id: str | None = None
    status: str = "draft"
    metadata: list[MetadataField] | None = None


class UpdateObjectRequest(BaseModel):
    updated_by: str = "system"
    status: str | None = None
    metadata: list[MetadataField] | None = None


class ObjectResponse(BaseModel):
    id: str
    object_type: str
    title: str
    status: str
    version: int
    created_by: str
    created_at: str
    metadata: dict[str, str] = {}
    events: list[str] = []


class ListObjectsResponse(BaseModel):
    items: list[ObjectResponse] = []
    total_count: int
    page: int
    page_size: int


def _repository(db: Session = Depends(get_db)) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


@router.get("", response_model=ListObjectsResponse)
def list_objects(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, le=100, description="items per page"),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> ListObjectsResponse:
    try:
        result = ListObjectsUseCase(repo).execute(
            ListObjectsQuery(page=page, page_size=page_size)
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return ListObjectsResponse(
        items=[ObjectResponse(**to_response(o)) for o in result.items],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/{object_id}", response_model=ObjectResponse)
def get_object(
    object_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> ObjectResponse:
    try:
        out = GetObjectUseCase(repo).execute(
            GetObjectQuery(object_id=ObjectId.parse(object_id))
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return ObjectResponse(**to_response(out))


@router.post("", response_model=ObjectResponse, status_code=status.HTTP_201_CREATED)
def create_object(
    req: CreateObjectRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> ObjectResponse:
    try:
        command = CreateObjectCommand(
            input=to_create_input(
                object_type=req.object_type,
                title=req.title,
                created_by=req.created_by,
                object_id=req.object_id,
                status=req.status,
                metadata=[m.model_dump() for m in (req.metadata or [])],
            )
        )
        out = CreateObjectUseCase(repo).execute(command)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except ObjectAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return ObjectResponse(**to_response(out))


@router.put("/{object_id}", response_model=ObjectResponse)
def update_object(
    object_id: str,
    req: UpdateObjectRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> ObjectResponse:
    try:
        command = UpdateObjectCommand(
            object_id=ObjectId.parse(object_id),
            input=to_update_input(
                object_id=object_id,
                updated_by=req.updated_by,
                status=req.status,
                metadata=[m.model_dump() for m in (req.metadata or [])],
            ),
        )
        out = UpdateObjectUseCase(repo).execute(command)
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return ObjectResponse(**to_response(out))


@router.delete(
    "/{object_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def delete_object(
    object_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> None:
    try:
        DeleteObjectUseCase(repo).execute(
            DeleteObjectCommand(object_id=ObjectId.parse(object_id))
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return None
