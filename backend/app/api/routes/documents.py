"""Documents API routes — Phase 2 vertical slice (full CRUD + upload/download).

Implements the six Document endpoints, all backed by the frozen Application
layer (a Document is a Universal Object with ``object_type = document``):
  - GET    /documents                  -> ListDocumentsUseCase   (paginated, ?object_id= filter)
  - GET    /documents/{id}             -> GetDocumentUseCase
  - POST   /documents        multipart -> CreateDocumentUseCase  (file + metadata)
  - PUT    /documents/{id}             -> UpdateDocumentUseCase
  - PATCH  /documents/{id}             -> UpdateDocumentUseCase  (same handler)
  - DELETE /documents/{id}             -> DeleteDocumentUseCase
  - GET    /documents/{id}/download    -> stored blob via the FileStorage port

The API depends only on the Application layer (use cases + ports) and on
adapters injected through FastAPI dependencies. No domain logic lives here —
mirrors ``objects.py`` one-to-one.
"""
from __future__ import annotations

import mimetypes

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.mappers.document_mapper import to_create_input, to_response, to_update_input
from app.application.commands.create_document import CreateDocumentCommand
from app.application.commands.delete_document import DeleteDocumentCommand
from app.application.commands.update_document import UpdateDocumentCommand
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.queries.get_document import GetDocumentQuery
from app.application.queries.list_documents import ListDocumentsQuery
from app.application.use_cases.documents.create_document import CreateDocumentUseCase
from app.application.use_cases.documents.delete_document import DeleteDocumentUseCase
from app.application.use_cases.documents.get_document import GetDocumentUseCase
from app.application.use_cases.documents.list_documents import ListDocumentsUseCase
from app.application.use_cases.documents.update_document import UpdateDocumentUseCase
from app.core.config import settings
from app.domain.exceptions import InvalidStateTransitionError
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.storage.local import LocalFileStorage

router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(get_current_user)])


class UpdateDocumentRequest(BaseModel):
    """JSON body for PUT/PATCH (mirrors the frontend ``UpdateDocumentPayload``)."""

    title: str | None = None
    object_id: str | None = None
    document_type: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    status: str | None = None
    uploaded_by: str = "system"


class DocumentResponseModel(BaseModel):
    """Response contract mirrored by ``frontend/src/types`` (DocumentResponse)."""

    id: str
    title: str
    object_id: str | None = None
    object_type: str | None = None
    object_title: str | None = None
    document_type: str
    description: str | None = None
    tags: list[str] = []
    file_name: str = ""
    file_size: int = 0
    mime_type: str = ""
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None = None
    url: str | None = None
    preview_url: str | None = None
    metadata: dict[str, str] = {}
    events: list[str] = []


class ListDocumentsResponseModel(BaseModel):
    items: list[DocumentResponseModel] = []
    total_count: int
    page: int
    page_size: int


def _repository(db: Session = Depends(get_db)) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


def get_storage() -> LocalFileStorage:
    """Storage dependency (overridable in tests; the configured adapter in prod)."""
    return LocalFileStorage(settings.storage_dir)


def _download_url(out, storage: LocalFileStorage) -> str | None:
    """Absolute download link when a stored blob exists, else ``None``."""
    if not out.file_path or not storage.exists(out.file_path):
        return None
    return (
        f"{settings.public_base_url}{settings.api_v1_prefix}"
        f"/documents/{out.id}/download"
    )


@router.get("", response_model=ListDocumentsResponseModel)
def list_documents(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, le=100, description="items per page"),
    object_id: str | None = Query(
        None, description="restrict to documents linked to this Object id"
    ),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> ListDocumentsResponseModel:
    try:
        result = ListDocumentsUseCase(repo).execute(
            ListDocumentsQuery(
                page=page,
                page_size=page_size,
                object_id=ObjectId.parse(object_id) if object_id else None,
            )
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return ListDocumentsResponseModel(
        items=[
            DocumentResponseModel(**to_response(o, url=_download_url(o, storage)))
            for o in result.items
        ],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/{document_id}", response_model=DocumentResponseModel)
def get_document(
    document_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> DocumentResponseModel:
    try:
        out = GetDocumentUseCase(repo).execute(
            GetDocumentQuery(object_id=ObjectId.parse(document_id))
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return DocumentResponseModel(**to_response(out, url=_download_url(out, storage)))


@router.post("", response_model=DocumentResponseModel, status_code=status.HTTP_201_CREATED)
def create_document(
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
    *,
    title: str = Form(...),
    document_type: str = Form(...),
    uploaded_by: str = Form(...),
    file: UploadFile = File(...),
    object_id: str | None = Form(None),
    description: str | None = Form(None),
    tags: str = Form("[]"),
    doc_status: str = Form("draft", alias="status"),
) -> DocumentResponseModel:
    content = file.file.read()
    file_name = file.filename or "unnamed"
    mime_type = (
        file.content_type
        or mimetypes.guess_type(file_name)[0]
        or "application/octet-stream"
    )
    try:
        out = CreateDocumentUseCase(repo, storage).execute(
            CreateDocumentCommand(
                input=to_create_input(
                    title=title,
                    document_type=document_type,
                    uploaded_by=uploaded_by,
                    file_name=file_name,
                    content=content,
                    mime_type=mime_type,
                    object_id=object_id,
                    description=description,
                    tags=tags,
                    status=doc_status,
                )
            )
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return DocumentResponseModel(**to_response(out, url=_download_url(out, storage)))


@router.put("/{document_id}", response_model=DocumentResponseModel)
@router.patch("/{document_id}", response_model=DocumentResponseModel)
def update_document(
    document_id: str,
    req: UpdateDocumentRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> DocumentResponseModel:
    try:
        out = UpdateDocumentUseCase(repo).execute(
            UpdateDocumentCommand(
                object_id=ObjectId.parse(document_id),
                input=to_update_input(
                    actor=req.uploaded_by,
                    title=req.title,
                    document_type=req.document_type,
                    description=req.description,
                    tags=req.tags,
                    status=req.status,
                    object_id=req.object_id,
                    object_id_provided="object_id" in req.model_fields_set,
                ),
            )
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (ValidationError, InvalidStateTransitionError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return DocumentResponseModel(**to_response(out, url=_download_url(out, storage)))


@router.delete(
    "/{document_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def delete_document(
    document_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> None:
    try:
        DeleteDocumentUseCase(repo, storage).execute(
            DeleteDocumentCommand(object_id=ObjectId.parse(document_id))
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return None


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> Response:
    try:
        out = GetDocumentUseCase(repo).execute(
            GetDocumentQuery(object_id=ObjectId.parse(document_id))
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    if not out.file_path or not storage.exists(out.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The stored file for this document was not found.",
        )
    safe_name = (out.file_name or out.title or "download").replace('"', "_")
    return Response(
        content=storage.read(out.file_path),
        media_type=out.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
