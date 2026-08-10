"""REST routes for the native document viewer (Sprint M10).

A dedicated router for the viewer surface, mirroring the
``eval_history.py`` precedent (a feature router sharing a prefix):

    GET    /documents/{document_id}/extracted-text   the linked intake
                                                     item's extracted text
                                                     (side-by-side panel)
    GET    /documents/{document_id}/annotations      list (page-ordered)
    POST   /documents/{document_id}/annotations      create (highlight /
                                                     note / bookmark)
    PUT    /documents/annotations/{annotation_id}    update page/payload
    DELETE /documents/annotations/{annotation_id}    204

All endpoints are authenticated; the router follows the module doctrine
(strict bodies, _not_found/_unprocessable mapping). The extraction
pipeline and the document module are untouched — this surface only
reads what already exists and persists viewer annotations.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, require_object_acl
from app.api.routes.documents import get_storage
from app.application.dtos.annotation import as_annotation_dict
from app.application.exceptions import ObjectNotFoundError
from app.application.services.document_annotation_service import (
    DocumentAnnotationService,
)
from app.domain.entities.object import UniversalObject
from app.infrastructure.db.session import get_db
from app.infrastructure.persistence.annotation_store import SQLAnnotationStore
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.storage.local import LocalFileStorage

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
    dependencies=[Depends(get_current_user), Depends(require_object_acl())],
)


def _service(db: Session) -> DocumentAnnotationService:
    return DocumentAnnotationService(
        SQLAlchemyObjectRepository(db), SQLAnnotationStore(db)
    )


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _unprocessable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
    )


class AnnotationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annotation_type: str
    page: int
    payload: dict[str, Any]


class AnnotationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int | None = None
    payload: dict[str, Any] | None = None


class AnnotationResponseModel(BaseModel):
    annotation_id: str
    document_id: str
    annotation_type: str
    page: int
    payload: dict[str, Any]
    created_by: str
    created_at: str
    updated_at: str | None = None


class ListAnnotationsResponseModel(BaseModel):
    items: list[AnnotationResponseModel]


class ExtractedTextResponseModel(BaseModel):
    text: str
    session_id: str
    item_id: str


@router.get("/{document_id}/extracted-text", response_model=ExtractedTextResponseModel)
def get_document_extracted_text(
    document_id: str,
    db: Session = Depends(get_db),
    storage: LocalFileStorage = Depends(get_storage),
) -> ExtractedTextResponseModel:
    """The linked intake item's extracted text (viewer right panel). 404
    when the document has no linked item or no extracted text."""
    result = _service(db).extracted_text(document_id, storage)
    if result is None:
        raise _not_found(
            "No extracted text is available for this document "
            "(no linked intake item or not extracted)."
        )
    return ExtractedTextResponseModel(**result)


@router.get("/{document_id}/annotations", response_model=ListAnnotationsResponseModel)
def list_annotations(
    document_id: str,
    db: Session = Depends(get_db),
) -> ListAnnotationsResponseModel:
    try:
        items = _service(db).list(document_id)
    except ObjectNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    return ListAnnotationsResponseModel(
        items=[AnnotationResponseModel(**as_annotation_dict(a)) for a in items]
    )


@router.post(
    "/{document_id}/annotations",
    response_model=AnnotationResponseModel,
    status_code=status.HTTP_201_CREATED,
)
def create_annotation(
    document_id: str,
    body: AnnotationCreateRequest,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> AnnotationResponseModel:
    try:
        annotation = _service(db).create(
            document_id=document_id,
            annotation_type=body.annotation_type,
            page=body.page,
            payload=body.payload,
            created_by=str(user.id),
        )
    except ObjectNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except ValueError as exc:
        raise _unprocessable(exc) from exc
    return AnnotationResponseModel(**as_annotation_dict(annotation))


@router.put("/annotations/{annotation_id}", response_model=AnnotationResponseModel)
def update_annotation(
    annotation_id: str,
    body: AnnotationUpdateRequest,
    db: Session = Depends(get_db),
) -> AnnotationResponseModel:
    try:
        annotation = _service(db).update(
            annotation_id,
            page=body.page,
            payload=body.payload,
        )
    except ObjectNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except ValueError as exc:
        raise _unprocessable(exc) from exc
    return AnnotationResponseModel(**as_annotation_dict(annotation))


@router.delete("/annotations/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_annotation(
    annotation_id: str,
    db: Session = Depends(get_db),
) -> Response:
    try:
        _service(db).delete(annotation_id)
    except ObjectNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
