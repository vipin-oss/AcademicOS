"""Document intake API (V3 ADR-067) — upload → understand → structured records.

Surface:
    POST /documents/analyze-upload       multipart upload → create document →
                                         analyze (classify + extract + dedupe +
                                         route) → DocumentAnalysis
    POST /documents/{document_id}/analyze   analyze an already-uploaded document

Both endpoints are permission-scoped (READ on the source document / ownership
on the created one), deterministic (no LLM dependency), and return an honest
analysis: classification + confidence + extracted fields + target module +
duplicate/conflict status + review requirement. Structured records are written
as claims (AUTO_SUGGESTED when high-confidence + conflict-free, PROPOSED
otherwise) bound to the source document for provenance.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.ai import get_ai_core
from app.api.dependencies.auth import get_current_user
from app.api.mappers.document_mapper import to_create_input
from app.api.routes.documents import (
    _index_direct_upload_content,
    _read_upload,
    get_storage,
)
from app.application.ai.core import AiCore
from app.application.commands.create_document import CreateDocumentCommand
from app.application.exceptions import ValidationError
from app.application.services.ai_semantic_extractor import AiSemanticExtractor
from app.application.services.claim_service import ClaimService
from app.application.services.document_annotation_service import DocumentAnnotationService
from app.application.services.document_intake import DocumentAnalysis, DocumentIntakeService
from app.application.services.domain_record_router import DomainRecordRouter, RouteOutcome
from app.application.use_cases.documents.create_document import CreateDocumentUseCase
from app.application.use_cases.object_acl import object_acl_scope
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectType, PermissionAction
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.session import get_db
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.persistence.annotation_store import SQLAnnotationStore
from app.infrastructure.persistence.claim_store import SQLClaimStore
from app.infrastructure.persistence.document_content_store import SQLDocumentContentStore
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.infrastructure.storage.local import LocalFileStorage

router = APIRouter(prefix="/documents", tags=["document-intake"])


class FieldConfidenceOut(BaseModel):
    """Per-field confidence information."""
    field_name: str
    predicate_id: str
    value: str
    confidence: float
    source: str  # "label" | "regex" | "prose" | "ai" | "agreement"
    risk: str    # "low" | "medium" | "high"
    status: str  # "auto_applied" | "proposed" | "review_required" | "conflict"


class AnalysisOut(BaseModel):
    document_id: str
    document_type_id: str | None
    confidence: float
    secondary_types: list[str]
    target_module: str
    status: str
    review_required: bool
    fields: list[dict]
    field_confidence: list[FieldConfidenceOut] = []
    records: list[dict]
    duplicates: list[dict]
    conflicts: list[dict]
    routing: list[dict] = []
    extraction_mode: str = "deterministic"
    ai_rejected: int = 0
    enrichment_status: str = "not_started"
    enrichment_timestamp: str | None = None


def _analysis_out(a: DocumentAnalysis, routing: list[RouteOutcome] | None = None) -> AnalysisOut:
    d = a.to_dict()
    d["routing"] = [
        {"module": r.module, "kind": r.kind, "object_id": r.object_id,
         "existing_id": r.existing_id, "reason": r.reason}
        for r in (routing or [])
    ]
    # Add field confidence from reconciled fields
    d["field_confidence"] = [
        FieldConfidenceOut(
            field_name=f.field_name,
            predicate_id=f.predicate_id,
            value=str(f.value),
            confidence=f.confidence,
            source=f.extractor,
            risk="medium",  # Default, will be enriched from field_candidate
            status="proposed" if f.extractor == "ai" else "auto_applied",
        )
        for f in a.fields
    ]
    return AnalysisOut(**d)


def _service(db: Session, ai_core: AiCore | None = None) -> DocumentIntakeService:
    store = SQLClaimStore(db)
    extractor = AiSemanticExtractor(ai_core) if ai_core is not None else None
    return DocumentIntakeService(ClaimService(store), store, ai_extractor=extractor)


def _fields_dict(a: DocumentAnalysis) -> dict[str, object]:
    """predicate_id -> normalized value (for domain-record routing)."""
    return {f.predicate_id: f.value for f in a.fields}


def _route_records(
    repo: SQLAlchemyObjectRepository,
    analysis: DocumentAnalysis,
    created_by: str,
    source_document_id: str,
) -> list[RouteOutcome]:
    """Create actual domain records when high-confidence and conflict-free."""
    if analysis.review_required or not analysis.document_type_id:
        return []
    fields = _fields_dict(analysis)
    fields["__types__"] = analysis.all_types()
    router = DomainRecordRouter(repo)
    return router.route(
        type_ids=analysis.all_types(),
        fields=fields,
        created_by=created_by,
        source_document_id=source_document_id,
        confidence=analysis.confidence,
    )


def _text_for(db: Session, storage, document_id: str) -> str:
    repo = SQLAlchemyObjectRepository(db)
    annotation = DocumentAnnotationService(
        repo, SQLAnnotationStore(db), content_store=SQLDocumentContentStore(db)
    )
    extracted = annotation.extracted_text(document_id, storage)
    return (extracted or {}).get("text") or ""


@router.post("/analyze-upload", response_model=AnalysisOut, status_code=status.HTTP_200_OK)
def analyze_upload(
    storage: LocalFileStorage = Depends(get_storage),
    db: Session = Depends(get_db),
    ai_core: AiCore = Depends(get_ai_core),
    *,
    title: str = Form(...),
    document_type: str = Form("pdf"),
    file: UploadFile = File(...),
    user: UniversalObject = Depends(get_current_user),
) -> AnalysisOut:
    """Upload a file, then run the document-intake pipeline on it."""
    import mimetypes

    repo = SQLAlchemyObjectRepository(db)
    content = _read_upload(file)
    file_name = file.filename or "unnamed"
    mime_type = file.content_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    try:
        out = CreateDocumentUseCase(repo, storage).execute(
            CreateDocumentCommand(input=to_create_input(
                title=title, document_type=document_type,
                uploaded_by=str(user.id), file_name=file_name,
                content=content, mime_type=mime_type,
            ))
        )
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    try:
        _index_direct_upload_content(
            db, document_id=str(out.id), version=out.version,
            file_name=file_name, content=content,
        )
    except Exception:  # noqa: BLE001 - indexing best-effort
        pass

    analysis = _service(db, ai_core).analyze(
        text=_text_for(db, storage, str(out.id)),
        filename=file_name,
        document_id=str(out.id),
        version=out.version,
        acl_scope=object_acl_scope(_load(db, repo, str(out.id))),
    )
    routing = _route_records(repo, analysis, str(user.id), str(out.id))
    db.commit()
    return _analysis_out(analysis, routing)


@router.post("/{document_id}/analyze", response_model=AnalysisOut)
def analyze_document(
    document_id: str,
    db: Session = Depends(get_db),
    storage: LocalFileStorage = Depends(get_storage),
    ai_core: AiCore = Depends(get_ai_core),
    user: UniversalObject = Depends(get_current_user),
) -> AnalysisOut:
    """Analyze an already-uploaded document (classify + extract + dedupe + route)."""
    repo = SQLAlchemyObjectRepository(db)
    doc = _load(db, repo, document_id)
    _require_read(doc, user)

    text = _text_for(db, storage, document_id)
    if not text:
        return _analysis_out(DocumentAnalysis(
            document_id=document_id, document_type_id=None, confidence=0.0,
            secondary_types=(), target_module="general_document",
            status="unknown", review_required=True,
        ))

    analysis = _service(db, ai_core).analyze(
        text=text,
        filename=doc.title or document_id,
        document_id=document_id,
        version=doc.version,
        acl_scope=object_acl_scope(doc),
    )
    routing = _route_records(repo, analysis, str(user.id), document_id)
    db.commit()

    # Get enrichment status from persisted metadata
    enrichment_status = doc.metadata.get_value("ai_enrichment_status") or "not_started"
    enrichment_timestamp = doc.metadata.get_value("ai_enrichment_timestamp")

    result = _analysis_out(analysis, routing)
    result.enrichment_status = enrichment_status
    result.enrichment_timestamp = enrichment_timestamp
    return result


def _load(db: Session, repo: SQLAlchemyObjectRepository, document_id: str) -> UniversalObject:
    doc = repo.get_by_id(ObjectId(document_id))
    if doc is None or doc.object_type is not ObjectType.DOCUMENT:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


def _require_read(doc: UniversalObject, user: UniversalObject) -> None:
    from app.application.use_cases.auth.helpers import get_roles

    if not ObjectPermissionEvaluator().can(
        principal={"sub": str(user.id), "roles": get_roles(user)},
        scope=object_acl_scope(doc),
        action=PermissionAction.READ,
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="No read permission on this document")
