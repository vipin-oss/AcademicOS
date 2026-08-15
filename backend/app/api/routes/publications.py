"""Publications API routes — reference-manager slice (full CRUD + tools).

Implements, all backed by the frozen Application layer (a Publication is a
Universal Object with ``object_type = publication``):
  - GET    /publications                        -> ListPublicationsUseCase
  - GET    /publications/export                 -> BibTeX / RIS / CSV (FR-PUB-003)
  - POST   /publications/import                 -> bulk import with duplicate report
  - GET    /publications/doi-lookup/{doi:path}  -> Crossref metadata (FR-PUB-006)
  - GET    /publications/{id}                   -> GetPublicationUseCase
  - POST   /publications                        -> CreatePublicationUseCase
  - PUT    /publications/{id}                   -> UpdatePublicationUseCase
  - PATCH  /publications/{id}                   -> UpdatePublicationUseCase (same handler)
  - DELETE /publications/{id}                   -> DeletePublicationUseCase
  - PUT    /publications/{id}/pdf               -> AttachPublicationPdfUseCase (attach/replace)
  - GET    /publications/{id}/pdf               -> download the attached PDF
  - GET    /publications/{id}/citation          -> bibliography.format_citation (APA/IEEE/…)

Static routes are declared BEFORE ``/{publication_id}`` so they are never
captured as an id. Mirrors ``objects.py`` / ``documents.py`` one-to-one.
"""
from __future__ import annotations

import mimetypes

from fastapi import (
    APIRouter,
    Depends,
    File,
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
from app.api.mappers.publication_mapper import (
    to_create_input,
    to_response,
    to_update_input,
)
from app.application.commands.attach_publication_pdf import (
    AttachPublicationPdfCommand,
)
from app.application.commands.create_publication import CreatePublicationCommand
from app.application.commands.delete_publication import DeletePublicationCommand
from app.application.commands.update_publication import UpdatePublicationCommand
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.ports.metadata_lookup import MetadataLookup
from app.application.queries.get_publication import GetPublicationQuery
from app.application.queries.list_publications import ListPublicationsQuery
from app.application.services.bibliography import (
    CITATION_STYLES,
    EXPORT_FORMATS,
    format_citation,
    serialize_records,
)
from app.application.use_cases.publications.attach_publication_pdf import (
    AttachPublicationPdfUseCase,
)
from app.application.use_cases.publications.create_publication import (
    CreatePublicationUseCase,
)
from app.application.use_cases.publications.delete_publication import (
    DeletePublicationUseCase,
)
from app.application.use_cases.publications.get_publication import GetPublicationUseCase
from app.application.use_cases.publications.import_publications import (
    ImportPublicationsCommand,
    ImportPublicationsUseCase,
)
from app.application.use_cases.publications.list_publications import (
    ListPublicationsUseCase,
)
from app.application.use_cases.publications.update_publication import (
    UpdatePublicationUseCase,
)
from app.core.config import settings
from app.domain.exceptions import InvalidStateTransitionError
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.session import get_db
from app.infrastructure.external import CrossrefMetadataLookup
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.storage.local import LocalFileStorage

router = APIRouter(prefix="/publications", tags=["publications"], dependencies=[Depends(get_current_user), Depends(require_object_acl())])


class CreatePublicationRequest(BaseModel):
    """JSON body for POST (manual entry). All bibliographic fields optional."""

    title: str
    publication_type: str
    uploaded_by: str
    status: str = "draft"
    pipeline_stage: str | None = None
    authors: list | None = None
    affiliations: list[str] | None = None
    abstract: str | None = None
    keywords: list[str] | None = None
    doi: str | None = None
    isbn: str | None = None
    issn: str | None = None
    publisher: str | None = None
    journal: str | None = None
    conference: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    year: int | None = None
    date: str | None = None
    language: str | None = None
    citation_count: int | None = None
    impact_factor: float | None = None
    quartile: str | None = None
    indexing: list[str] | None = None
    publisher_url: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    collections: list[str] | None = None
    links: dict | None = None


class UpdatePublicationRequest(CreatePublicationRequest):
    """JSON body for PUT/PATCH (partial semantics; every field optional)."""

    title: str | None = None
    publication_type: str | None = None
    uploaded_by: str = "system"
    status: str | None = None


class ImportPublicationRequest(BaseModel):
    fmt: str
    text: str
    uploaded_by: str


class PublicationResponseModel(BaseModel):
    id: str
    title: str
    publication_type: str
    pipeline_stage: str | None = None
    authors: list[dict] = []
    affiliations: list[str] = []
    abstract: str | None = None
    keywords: list[str] = []
    doi: str | None = None
    isbn: str | None = None
    issn: str | None = None
    publisher: str | None = None
    journal: str | None = None
    conference: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    year: int | None = None
    date: str | None = None
    language: str | None = None
    citation_count: int = 0
    impact_factor: float | None = None
    quartile: str | None = None
    indexing: list[str] = []
    publisher_url: str | None = None
    notes: str | None = None
    tags: list[str] = []
    collections: list[str] = []
    status: str
    version: int
    uploaded_by: str
    created_at: str
    updated_at: str | None = None
    pdf_file_name: str | None = None
    pdf_file_size: int = 0
    pdf_mime_type: str | None = None
    pdf_url: str | None = None
    links: dict[str, list[dict]] = {}
    metadata: dict[str, str] = {}
    events: list[str] = []


class ListPublicationsResponseModel(BaseModel):
    items: list[PublicationResponseModel] = []
    total_count: int
    page: int
    page_size: int


class ImportResultResponseModel(BaseModel):
    created: list[str] = []
    duplicates: list[dict] = []
    errors: list[dict] = []


class CitationResponseModel(BaseModel):
    style: str
    citation: str


def _repository(db: Session = Depends(get_db)) -> SQLAlchemyObjectRepository:
    return SQLAlchemyObjectRepository(db)


def get_storage() -> LocalFileStorage:
    """Storage dependency (overridable in tests; the configured adapter in prod)."""
    return LocalFileStorage(settings.storage_dir)


def get_metadata_lookup() -> MetadataLookup:
    """External metadata provider dependency (overridable in tests)."""
    return CrossrefMetadataLookup()


def _pdf_url(out, storage: LocalFileStorage) -> str | None:
    """Absolute PDF link when an attached blob exists, else ``None``."""
    if not out.pdf_file_path or not storage.exists(out.pdf_file_path):
        return None
    return f"{settings.public_base_url}{settings.api_v1_prefix}/publications/{out.id}/pdf"


def _list_query(
    page: int,
    page_size: int,
    q: str | None,
    publication_type: str | None,
    year: int | None,
    quartile: str | None,
    pipeline_stage: str | None,
    pub_status: str | None,
    object_id: str | None,
) -> ListPublicationsQuery:
    return ListPublicationsQuery(
        page=page,
        page_size=page_size,
        q=q or None,
        publication_type=publication_type or None,
        year=year,
        quartile=quartile or None,
        pipeline_stage=pipeline_stage or None,
        status=pub_status or None,
        object_id=ObjectId.parse(object_id) if object_id else None,
    )


@router.get("", response_model=ListPublicationsResponseModel)
def list_publications(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, le=100, description="items per page"),
    q: str | None = Query(None, description="title/authors/DOI/venue/keywords/publisher"),
    publication_type: str | None = Query(None),
    year: int | None = Query(None, ge=1000, le=2100),
    quartile: str | None = Query(None),
    pipeline_stage: str | None = Query(None),
    pub_status: str | None = Query(None, alias="status"),
    object_id: str | None = Query(
        None, description="restrict to publications linked to this Object id"
    ),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> ListPublicationsResponseModel:
    try:
        result = ListPublicationsUseCase(repo).execute(
            _list_query(page, page_size, q, publication_type, year, quartile,
                        pipeline_stage, pub_status, object_id)
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return ListPublicationsResponseModel(
        items=[
            PublicationResponseModel(**to_response(o, pdf_url=_pdf_url(o, storage)))
            for o in result.items
        ],
        total_count=result.total_count,
        page=result.page,
        page_size=result.page_size,
    )


# --- static routes are declared BEFORE /{publication_id} on purpose --------


@router.get("/export")
def export_publications(
    fmt: str = Query(..., description=f"one of: {', '.join(EXPORT_FORMATS)}"),
    q: str | None = Query(None),
    publication_type: str | None = Query(None),
    year: int | None = Query(None, ge=1000, le=2100),
    quartile: str | None = Query(None),
    pipeline_stage: str | None = Query(None),
    pub_status: str | None = Query(None, alias="status"),
    object_id: str | None = Query(None),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> Response:
    fmt = (fmt or "").lower()
    if fmt not in EXPORT_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"fmt must be one of: {', '.join(EXPORT_FORMATS)}.",
        )
    use_case = ListPublicationsUseCase(repo)
    records: list[dict] = []
    page = 1
    try:
        while True:  # walk every page of the same filtered query
            result = use_case.execute(
                _list_query(page, 100, q, publication_type, year, quartile,
                            pipeline_stage, pub_status, object_id)
            )
            records.extend(o.to_record() for o in result.items)
            if len(records) >= result.total_count or not result.items:
                break
            page += 1
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    text = serialize_records(records, fmt)
    media, ext = {
        "bibtex": ("application/x-bibtex", "bib"),
        "ris": ("application/x-research-info-systems", "ris"),
        "csv": ("text/csv", "csv"),
    }[fmt]
    return Response(
        content=text,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="publications.{ext}"'},
    )


@router.post("/import", response_model=ImportResultResponseModel)
def import_publications(
    req: ImportPublicationRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    user: UniversalObject = Depends(get_current_user),
) -> ImportResultResponseModel:
    try:
        result = ImportPublicationsUseCase(repo).execute(
            ImportPublicationsCommand(fmt=req.fmt, text=req.text, uploaded_by=str(user.id))
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return ImportResultResponseModel(
        created=result.created, duplicates=result.duplicates, errors=result.errors
    )


@router.get("/doi-lookup/{doi:path}")
def doi_lookup(
    doi: str,
    lookup: MetadataLookup = Depends(get_metadata_lookup),
) -> dict:
    try:
        record = lookup.lookup(doi)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Crossref record found for DOI {doi!r}.",
        )
    return record


@router.get("/{publication_id}", response_model=PublicationResponseModel)
def get_publication(
    publication_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> PublicationResponseModel:
    try:
        out = GetPublicationUseCase(repo).execute(
            GetPublicationQuery(object_id=ObjectId.parse(publication_id))
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return PublicationResponseModel(**to_response(out, pdf_url=_pdf_url(out, storage)))


@router.post("", response_model=PublicationResponseModel, status_code=status.HTTP_201_CREATED)
def create_publication(
    req: CreatePublicationRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
) -> PublicationResponseModel:
    try:
        out = CreatePublicationUseCase(repo).execute(
            CreatePublicationCommand(input=to_create_input(body={**req.model_dump(), "uploaded_by": str(user.id)}))
        )
    except ObjectAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return PublicationResponseModel(**to_response(out, pdf_url=_pdf_url(out, storage)))


@router.put("/{publication_id}", response_model=PublicationResponseModel)
@router.patch("/{publication_id}", response_model=PublicationResponseModel)
def update_publication(
    publication_id: str,
    req: UpdatePublicationRequest,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
    user: UniversalObject = Depends(get_current_user),
) -> PublicationResponseModel:
    try:
        out = UpdatePublicationUseCase(repo).execute(
            UpdatePublicationCommand(
                object_id=ObjectId.parse(publication_id),
                input=to_update_input(body={**req.model_dump(exclude_unset=True), "updated_by": str(user.id)}),
            )
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ObjectAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except (ValidationError, InvalidStateTransitionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return PublicationResponseModel(**to_response(out, pdf_url=_pdf_url(out, storage)))


@router.delete("/{publication_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_publication(
    publication_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> None:
    try:
        DeletePublicationUseCase(repo, storage).execute(
            DeletePublicationCommand(object_id=ObjectId.parse(publication_id))
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return None


@router.put("/{publication_id}/pdf", response_model=PublicationResponseModel)
def attach_publication_pdf(
    publication_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
    *,
    file: UploadFile = File(...),
    uploaded_by: str = "system",
) -> PublicationResponseModel:
    content = file.file.read()
    file_name = file.filename or "publication.pdf"
    mime_type = (
        file.content_type or mimetypes.guess_type(file_name)[0] or "application/pdf"
    )
    try:
        out = AttachPublicationPdfUseCase(repo, storage).execute(
            AttachPublicationPdfCommand(
                object_id=ObjectId.parse(publication_id),
                file_name=file_name,
                content=content,
                mime_type=mime_type,
                actor=uploaded_by,
            )
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return PublicationResponseModel(**to_response(out, pdf_url=_pdf_url(out, storage)))


@router.get("/{publication_id}/pdf")
def download_publication_pdf(
    publication_id: str,
    repo: SQLAlchemyObjectRepository = Depends(_repository),
    storage: LocalFileStorage = Depends(get_storage),
) -> Response:
    try:
        out = GetPublicationUseCase(repo).execute(
            GetPublicationQuery(object_id=ObjectId.parse(publication_id))
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if not out.pdf_file_path or not storage.exists(out.pdf_file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No PDF is attached to this publication.",
        )
    safe_name = (out.pdf_file_name or out.title or "publication").replace('"', "_")
    return Response(
        content=storage.read(out.pdf_file_path),
        media_type=out.pdf_mime_type or "application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.get("/{publication_id}/citation", response_model=CitationResponseModel)
def cite_publication(
    publication_id: str,
    style: str = Query("apa", description=f"one of: {', '.join(CITATION_STYLES)}"),
    repo: SQLAlchemyObjectRepository = Depends(_repository),
) -> CitationResponseModel:
    style = (style or "apa").lower()
    if style not in CITATION_STYLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"style must be one of: {', '.join(CITATION_STYLES)}.",
        )
    try:
        out = GetPublicationUseCase(repo).execute(
            GetPublicationQuery(object_id=ObjectId.parse(publication_id))
        )
    except ObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return CitationResponseModel(
        style=style, citation=format_citation(out.to_record(), style)
    )
