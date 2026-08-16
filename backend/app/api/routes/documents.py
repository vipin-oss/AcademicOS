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
    BackgroundTasks,
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

from app.api.dependencies.auth import get_current_user, require_object_acl
from app.domain.entities.object import UniversalObject
from app.api.mappers.document_mapper import to_create_input, to_response, to_update_input
from app.application.commands.create_document import CreateDocumentCommand
from app.application.commands.delete_document import DeleteDocumentCommand
from app.application.commands.update_document import UpdateDocumentCommand
from app.application.dtos.extraction import format_of
from app.application.dtos.intake import MAX_FILE_BYTES
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.intake.pipeline import human_bytes
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
from app.infrastructure.extraction import build_document_parsers
from app.infrastructure.persistence.document_content_store import SQLDocumentContentStore
from app.application.services.document_chunking import content_hash
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.storage.local import LocalFileStorage

import logging

_log = logging.getLogger(__name__)


def _infer_doc_type(file_name: str, mime_type: str) -> str:
    """Infer document type from filename extension and MIME type."""
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    ext_map = {
        "pdf": "pdf", "doc": "docx", "docx": "docx",
        "xls": "xlsx", "xlsx": "xlsx",
        "ppt": "pptx", "pptx": "pptx",
        "txt": "txt", "md": "txt", "csv": "txt",
        "zip": "zip", "7z": "zip", "rar": "zip",
        "png": "image", "jpg": "image", "jpeg": "image",
        "gif": "image", "webp": "image", "svg": "image", "bmp": "image",
        "mp4": "video", "mov": "video", "webm": "video",
    }
    if ext in ext_map:
        return ext_map[ext]
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    if mime_type == "application/pdf":
        return "pdf"
    if "spreadsheet" in mime_type or "excel" in mime_type:
        return "xlsx"
    if "presentation" in mime_type or "powerpoint" in mime_type:
        return "pptx"
    if "word" in mime_type:
        return "docx"
    return "unknown"


def _enrich_document_background(document_id: str, user_id: str) -> None:
    """Background task: enrich a document with AI after upload.

    Runs asynchronously after the upload response is sent to the user.
    Uses a new database session (background tasks run after the request session closes).
    Errors are logged but never propagate — the upload already succeeded.
    """
    try:
        from app.infrastructure.db.session import SessionLocal
        from app.api.dependencies.ai import get_ai_core
        from app.infrastructure.persistence.annotation_store import SQLAnnotationStore
        from app.infrastructure.persistence.document_content_store import SQLDocumentContentStore
        from app.application.services.document_annotation_service import DocumentAnnotationService
        from app.application.use_cases.ai.enrich_document import EnrichDocumentUseCase
        from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
        from app.domain.value_objects.enums import ObjectType, ObjectStatus
        from app.domain.value_objects.object_id import ObjectId

        db = SessionLocal()
        try:
            repo = SQLAlchemyObjectRepository(db)
            try:
                core = get_ai_core()
            except Exception:
                _log.debug("Background enrichment skipped: AI Core not available.")
                return

            if not core.config.enabled or not core.config.feature_flags.get("enrichment", False):
                return

            annotation_service = DocumentAnnotationService(
                repo, SQLAnnotationStore(db), content_store=SQLDocumentContentStore(db)
            )
            evaluator = ObjectPermissionEvaluator()

            user_obj = UniversalObject.create(
                object_type=ObjectType.USER,
                title="background",
                created_by="system",
                status=ObjectStatus.ACTIVE,
                object_id=ObjectId(user_id) if user_id.startswith("obj:") else ObjectId(f"obj:user:{user_id}"),
            )

            use_case = EnrichDocumentUseCase(repo, annotation_service, evaluator, core)
            try:
                result = use_case.execute(document_id, user_obj, None)
                if result.available:
                    _log.info(
                        "Background enrichment completed for %s: title=%r, tags=%s",
                        document_id, result.title, result.tags,
                    )
                else:
                    _log.debug("Background enrichment for %s: AI returned no results.", document_id)
            except Exception as exc:
                _log.debug("Background enrichment failed for %s: %s", document_id, exc)
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — never crash the background task
        _log.debug("Background enrichment error for %s: %s", document_id, exc)


router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(get_current_user), Depends(require_object_acl())])


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


def _index_direct_upload_content(
    db: Session,
    *,
    document_id: str,
    version: int,
    file_name: str,
    content: bytes,
) -> None:
    """Direct-upload content projection (Fix A, M27 seam).

    After a document is created, parse the already-in-memory upload bytes
    with the EXISTING M2 parser registry (``build_document_parsers()``) and
    write the EXISTING ``document_contents`` projection through the same
    store the intake commit uses (``SQLDocumentContentStore``). The content
    row is keyed by the document id, so the existing SQL content-search leg
    (``SQLAlchemySearchRepository.search``) and the annotation service's
    extracted-text fallback find the body without any new architecture.

    Graceful degradation contract: an unsupported format, a parse failure,
    or empty extracted text simply skips the content row — the upload
    itself has already succeeded and title/metadata stay searchable
    (mirrors the intake pipeline's per-item isolation).
    """
    extension = file_name.rsplit(".", 1)[-1] if "." in file_name else ""
    parser = build_document_parsers().get(format_of(extension) or "")
    if parser is None:
        return
    try:
        result = parser.parse(content)
    except Exception:  # noqa: BLE001 — content indexing must never fail the upload
        _log.warning(
            "Direct-upload content indexing skipped for %r: parse failed.",
            file_name,
            exc_info=True,
        )
        return
    text = (result.text or "").strip()
    if not text:
        return
    SQLDocumentContentStore(db).upsert(
        object_id=document_id,
        version=version,
        content_text=text,
        # Self-provenance: a direct upload has no intake item, so the row
        # records the document itself as its source (NOT NULL column).
        source_item_id=document_id,
        content_hash=content_hash(text),
    )
    db.commit()


def _read_upload(file: UploadFile) -> bytes:
    """Read an upload into memory with the shared 512 MB cap (413 on
    oversize). Chunked so an oversized file never loads into RAM, and the
    ``size`` fast path (Starlette >= 0.40) skips the read entirely when the
    client declared it. Mirrors the intake pipeline's ``MAX_FILE_BYTES``
    guard."""
    declared = getattr(file, "size", None)
    if declared is not None and declared > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {human_bytes(MAX_FILE_BYTES)} upload cap.",
        )
    content = bytearray()
    while chunk := file.file.read(1024 * 1024):
        content.extend(chunk)
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds the {human_bytes(MAX_FILE_BYTES)} upload cap.",
            )
    return bytes(content)


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
    db: Session = Depends(get_db),
    *,
    bg_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    document_type: str | None = Form(None),
    uploaded_by: str | None = Form(None),
    object_id: str | None = Form(None),
    description: str | None = Form(None),
    tags: str = Form("[]"),
    doc_status: str = Form("draft", alias="status"),
    user: UniversalObject = Depends(get_current_user),
) -> DocumentResponseModel:
    content = _read_upload(file)
    file_name = file.filename or "unnamed"
    mime_type = (
        file.content_type
        or mimetypes.guess_type(file_name)[0]
        or "application/octet-stream"
    )
    # Auto-derive fields when not provided by the user.
    auto_title = title if title and title.strip() else file_name.rsplit(".", 1)[0] if "." in file_name else file_name
    auto_doc_type = document_type if document_type and document_type.strip() else _infer_doc_type(file_name, mime_type)
    auto_uploaded_by = str(user.id)
    # V3 M11 (ADR-058): the canonical sync pipeline — hash + quarantine
    # decision run identically for every entry point.
    from app.application.services.document_pipeline import DocumentPipeline

    decision = DocumentPipeline.decision(file_name, mime_type, content)
    try:
        out = CreateDocumentUseCase(repo, storage).execute(
            CreateDocumentCommand(
                input=to_create_input(
                    title=auto_title,
                    document_type=auto_doc_type,
                    uploaded_by=auto_uploaded_by,
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
    # V3 M11 (ADR-058): record an immutable revision and skip content indexing
    # for quarantined blobs (stored, but never indexed/claimed).
    try:
        from app.application.ports.document_revision_store import DocumentRevision
        from app.infrastructure.persistence.document_revision_store import (
            SQLDocumentRevisionStore,
        )
        import datetime as _dt
        import uuid as _uuid

        revision_store = SQLDocumentRevisionStore(db)
        revision = DocumentRevision(
            id=_uuid.uuid4().hex,
            document_id=str(out.id),
            revision_version=revision_store.next_version(str(out.id)),
            file_name=file_name,
            content_hash=decision.content_hash,
            mime_type=mime_type,
            file_size=len(content),
            storage_key=str(out.id),
            quarantined=decision.quarantine != "clean",
            quarantine_reason=decision.quarantine_reason,
            created_at=_dt.datetime.now(_dt.UTC).isoformat(),
        )
        revision_store.add(revision)
        db.commit()
        if decision.quarantine == "clean":
            _index_direct_upload_content(
                db,
                document_id=str(out.id),
                version=out.version,
                file_name=file_name,
                content=content,
            )
        else:
            _log.warning(
                "Quarantined upload %r: %s (stored, not indexed).",
                file_name,
                decision.quarantine_reason,
            )
    except Exception:  # noqa: BLE001 — revision/indexing is best-effort
        _log.warning(
            "Direct-upload revision/indexing failed for %r; upload succeeded.",
            file_name,
            exc_info=True,
        )
    # Schedule background AI enrichment (non-blocking).
    if decision.quarantine == "clean" and settings.ai_enabled:
        try:
            bg_tasks.add_task(
                _enrich_document_background,
                document_id=str(out.id),
                user_id=str(user.id),
            )
        except Exception:  # noqa: BLE001 — enrichment scheduling must never fail the upload
            _log.debug("Background enrichment scheduling skipped (not available).")
    return DocumentResponseModel(**to_response(out, url=_download_url(out, storage)))


@router.put("/{document_id}", response_model=DocumentResponseModel)
@router.patch("/{document_id}", response_model=DocumentResponseModel)
def update_document(
    document_id: str,
    req: UpdateDocumentRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
) -> DocumentResponseModel:
    try:
        out = UpdateDocumentUseCase(repo).execute(
            UpdateDocumentCommand(
                object_id=ObjectId.parse(document_id),
                input=to_update_input(
                    actor=str(user.id),
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
