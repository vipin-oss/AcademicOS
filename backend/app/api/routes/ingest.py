"""L2 ingestion API (ADR-028 / ADR-022).

``POST /documents/ingest`` — multipart file upload that composes the EXISTING
document-creation flow with the L2 extraction orchestrator: the file is stored
and a ``document`` object is created (reusing the frozen ``CreateDocumentUseCase``),
then the blob is run through the L2 orchestrator to produce L1 CDM blocks and
the content projection. Unsupported/corrupt sources are reported honestly
(``unsupported``/``error``), never silently dropped. Additive — no second
upload system.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.application.commands.create_document import CreateDocumentCommand
from app.application.dtos.document import CreateDocumentInput
from app.application.dtos.extraction import format_of
from app.application.services.cdm_service import CdmService
from app.application.services.extraction_orchestrator import ExtractionOrchestrator
from app.application.services.nir_mapper import NirMapper
from app.application.use_cases.documents.create_document import (
    CreateDocumentUseCase,
    storage_key_for,
)
from app.core.config import settings
from app.domain.value_objects.object_id import ObjectId
from app.domain.value_objects.source import MediaKind
from app.infrastructure.db.session import get_db
from app.infrastructure.extraction.registry import (
    build_container_expander,
    build_structured_parsers,
)
from app.infrastructure.persistence.cdm_store import SQLCdmStore
from app.infrastructure.persistence.document_content_store import SQLDocumentContentStore
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.storage.local.local_storage import LocalFileStorage

_log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/documents",
    tags=["ingestion"],
    dependencies=[Depends(get_current_user)],
)


class MemberOut(BaseModel):
    path: str
    ok: bool
    error: str | None = None
    document_id: str | None = None
    media_kind: str | None = None
    elements: int = 0
    needs_ocr: bool = False


class IngestResponse(BaseModel):
    document_id: str
    title: str
    file_name: str
    status: str
    media_kind: str
    family: str | None = None
    elements: int = 0
    pages: int = 0
    slides: int = 0
    sheets: int = 0
    images: int = 0
    needs_ocr: bool = False
    warning: str | None = None
    members: list[MemberOut] = []


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_document(
    file: UploadFile = File(...),
    title: str = Form(default=""),
    document_type: str = Form(default="other"),
    object_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> IngestResponse:
    """Upload + L2-extract a document of any supported media kind.

    Returns an honest ingestion status; the document is created regardless so
    the blob and provenance are never lost. ``ocr_enabled`` is OFF by default.
    """
    file_name = file.filename or "unnamed"
    content = file.file.read()
    ext = file_name.rsplit(".", 1)[-1] if "." in file_name else ""
    family = format_of(ext)
    media_kind = MediaKind.from_extension(ext)

    repo = SQLAlchemyObjectRepository(db)
    storage = LocalFileStorage(settings.storage_dir)

    # reuse the frozen create flow (stores blob + creates document object)
    command = CreateDocumentCommand(
        CreateDocumentInput(
            title=title or file_name,
            document_type=document_type,
            uploaded_by="system",
            file_name=file_name,
            file_size=len(content),
            mime_type=(file.content_type or ""),
            content=content,
            object_id=ObjectId.parse(object_id) if object_id else None,
            status="active",
        )
    )
    try:
        created = CreateDocumentUseCase(repo, storage).execute(command)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    document = repo.get_by_id(created.id)
    if document is None:
        raise HTTPException(status_code=500, detail="Document not found after create.")

    # L2 orchestrator
    cdm_service = CdmService(SQLCdmStore(db))
    mapper = NirMapper(cdm_service)
    orchestrator = ExtractionOrchestrator(
        parsers=build_structured_parsers(),
        expander=build_container_expander(),
        mapper=mapper,
        content_store=SQLDocumentContentStore(db),
    )
    result = orchestrator.ingest_blob(
        document=document,
        blob=content,
        file_name=file_name,
        extension=ext,
        family=family,
        media_kind=media_kind,
        version=created.version or 1,
        blob_key=storage_key_for(document.id, file_name),
    )
    repo.save(document)
    db.commit()

    members = [
        MemberOut(
            path=m.path, ok=m.ok, error=m.error,
            document_id=m.document_id, media_kind=m.media_kind,
            elements=m.elements, needs_ocr=m.needs_ocr,
        )
        for m in result.members
    ]
    return IngestResponse(
        document_id=result.source_id, title=document.title, file_name=file_name,
        status=result.status, media_kind=result.media_kind, family=result.family,
        elements=result.elements, pages=result.pages, slides=result.slides,
        sheets=result.sheets, images=result.images, needs_ocr=result.needs_ocr,
        warning=result.warning, members=members,
    )
