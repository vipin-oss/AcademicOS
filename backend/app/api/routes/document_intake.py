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
from app.application.services.entity_linking import EntityLinkingService
from app.application.services.entity_resolution import MatchResult, match_entities
from app.application.services.document_intake import DocumentAnalysis, DocumentIntakeService
from app.application.services.domain_record_router import DomainRecordRouter, RouteOutcome
from app.application.services.notification_service import (
    NotificationService,
    notify_conflicts_detected,
    notify_document_analyzed,
)
from app.infrastructure.persistence.notification_store import SQLNotificationStore
from app.application.ports.entity_match_store import MatchDecision
from app.infrastructure.persistence.entity_match_store import SQLEntityMatchStore
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


class EntityMatchOut(BaseModel):
    """Cross-document entity match."""
    target_doc_id: str
    confidence: float
    outcome: str  # "high", "medium", "low", "conflict"
    signals: list[dict]  # List of {signal_type, confidence, evidence}


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
    entity_matches: list[EntityMatchOut] = []
    extraction_mode: str = "deterministic"
    ai_rejected: int = 0
    enrichment_status: str = "not_started"
    enrichment_timestamp: str | None = None


def _analysis_out(
    a: DocumentAnalysis,
    routing: list[RouteOutcome] | None = None,
    entity_matches: list | None = None,
) -> AnalysisOut:
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
    # Add entity matches (cross-document intelligence)
    d["entity_matches"] = [
        EntityMatchOut(
            target_doc_id=m.target_doc_id,
            confidence=m.confidence,
            outcome=m.outcome,
            signals=[
                {"signal_type": s.signal_type, "confidence": s.confidence, "evidence": s.evidence}
                for s in m.signals
            ],
        )
        for m in (entity_matches or [])
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

    # Entity resolution: find existing records that might be the same entity
    entity_matches = []
    if analysis.document_type_id and analysis.fields:
        try:
            fields = _fields_dict(analysis)
            router = DomainRecordRouter(repo)
            entity_matches = router.find_entity_matches(
                source_document_id=document_id,
                fields=fields,
                type_ids=analysis.all_types(),
                owner_id=str(user.id),
            )
        except Exception:  # noqa: BLE001 - entity resolution is best-effort
            pass

    db.commit()

    # Generate notifications for meaningful events (Revision #18)
    _maybe_notify(db, str(user.id), document_id, doc.title or document_id,
                  analysis, entity_matches)

    # Get enrichment status from persisted metadata
    enrichment_status = doc.metadata.get_value("ai_enrichment_status") or "not_started"
    enrichment_timestamp = doc.metadata.get_value("ai_enrichment_timestamp")

    result = _analysis_out(analysis, routing, entity_matches)
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


def _maybe_notify(
    db: Session,
    user_id: str,
    document_id: str,
    document_title: str,
    analysis: DocumentAnalysis,
    entity_matches: list,
) -> None:
    """Generate notifications for meaningful events only.

    Does NOT notify for every successful upload.
    Only notifies when professor action is needed.
    """
    try:
        notif_svc = NotificationService(SQLNotificationStore(db))

        # 1. Entity match requiring review
        medium_matches = [m for m in entity_matches if m.outcome == "medium"]
        if medium_matches:
            notif_svc.create(
                user_id=user_id,
                notification_type="entity_match",
                title="Possible related document found",
                message=f'"{document_title}" may refer to the same publication as another document.',
                action_url=f"/documents/{document_id}",
                metadata={"document_id": document_id, "match_count": len(medium_matches)},
            )

        # 2. Conflicts detected
        if analysis.conflicts:
            notify_conflicts_detected(
                notif_svc, user_id, document_id, document_title,
                len(analysis.conflicts),
            )

        # 3. Review required (not from conflicts — those are handled above)
        if analysis.review_required and not analysis.conflicts and not entity_matches:
            notify_document_analyzed(
                notif_svc, user_id, document_id, document_title,
                len(analysis.fields), review_required=True,
            )

        db.commit()
    except Exception:  # noqa: BLE001 - notifications are best-effort
        db.rollback()


class LinkRequest(BaseModel):
    """Request to link two documents."""
    target_doc_id: str
    confidence: float = 0.0
    evidence: str = ""


class LinkResponse(BaseModel):
    """Response for entity linking operation."""
    success: bool
    source_doc_id: str
    target_doc_id: str
    already_linked: bool = False
    error: str | None = None


class RelatedDocsResponse(BaseModel):
    """Response for related documents query."""
    document_id: str
    related: list[dict]


@router.post("/{document_id}/link", response_model=LinkResponse)
def link_documents(
    document_id: str,
    body: LinkRequest,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> LinkResponse:
    """Link two documents as referring to the same academic entity.

    Creates a RELATED_TO relationship between the source document
    and the target document. Idempotent — no duplicate relationships.
    """
    repo = SQLAlchemyObjectRepository(db)
    doc = _load(db, repo, document_id)
    _require_read(doc, user)

    linking_service = EntityLinkingService(repo)
    result = linking_service.create_link(
        source_doc_id=document_id,
        target_doc_id=body.target_doc_id,
        confidence=body.confidence,
        evidence=body.evidence or "Manual link confirmation",
        actor=str(user.id),
    )

    if result.success:
        db.commit()

    return LinkResponse(
        success=result.success,
        source_doc_id=result.source_doc_id,
        target_doc_id=result.target_doc_id,
        already_linked=result.already_linked,
        error=result.error,
    )


@router.post("/{document_id}/confirm-match/{target_doc_id}", response_model=LinkResponse)
def confirm_entity_match(
    document_id: str,
    target_doc_id: str,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> LinkResponse:
    """Confirm an entity match and create a relationship.

    This is the professor-friendly endpoint for confirming that two
    documents refer to the same academic entity.
    Idempotent — repeated confirmation does not create duplicate relationships.
    """
    repo = SQLAlchemyObjectRepository(db)
    doc = _load(db, repo, document_id)
    _require_read(doc, user)

    # Verify target exists and user has access
    target = repo.get_by_id(ObjectId(target_doc_id))
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Target document not found")

    # Persist the confirmation decision
    match_store = SQLEntityMatchStore(db)
    match_store.put(
        source_doc_id=document_id,
        target_doc_id=target_doc_id,
        confidence=1.0,
        evidence="Confirmed by user",
        decision=MatchDecision.CONFIRMED,
        decided_by=str(user.id),
    )

    # Create the link
    linking_service = EntityLinkingService(repo)
    result = linking_service.create_link(
        source_doc_id=document_id,
        target_doc_id=target_doc_id,
        confidence=1.0,  # User-confirmed = highest confidence
        evidence="Confirmed by user",
        actor=str(user.id),
    )

    if result.success:
        db.commit()

    return LinkResponse(
        success=result.success,
        source_doc_id=result.source_doc_id,
        target_doc_id=result.target_doc_id,
        already_linked=result.already_linked,
        error=result.error,
    )


@router.get("/{document_id}/related", response_model=RelatedDocsResponse)
def get_related_documents(
    document_id: str,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> RelatedDocsResponse:
    """Get all documents related to the given document."""
    repo = SQLAlchemyObjectRepository(db)
    doc = _load(db, repo, document_id)
    _require_read(doc, user)

    linking_service = EntityLinkingService(repo)
    related = linking_service.get_related_documents(document_id)

    return RelatedDocsResponse(
        document_id=document_id,
        related=related,
    )


@router.post("/{document_id}/reject-match/{target_doc_id}", response_model=LinkResponse)
def reject_entity_match(
    document_id: str,
    target_doc_id: str,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> LinkResponse:
    """Reject an entity match — professor says these documents are NOT the same entity.

    Persists the rejection so it doesn't reappear after re-analysis.
    Does NOT create a relationship.
    Idempotent — repeated rejection does not create duplicates.
    """
    repo = SQLAlchemyObjectRepository(db)
    doc = _load(db, repo, document_id)
    _require_read(doc, user)

    # Verify target exists and user has access
    target = repo.get_by_id(ObjectId(target_doc_id))
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Target document not found")

    # Persist the rejection
    match_store = SQLEntityMatchStore(db)
    match_store.put(
        source_doc_id=document_id,
        target_doc_id=target_doc_id,
        confidence=0.0,
        evidence="Rejected by user",
        decision=MatchDecision.REJECTED,
        decided_by=str(user.id),
    )
    db.commit()

    return LinkResponse(
        success=True,
        source_doc_id=document_id,
        target_doc_id=target_doc_id,
        already_linked=False,
        error=None,
    )


class PendingMatchesResponse(BaseModel):
    """Response for pending entity matches."""
    document_id: str
    pending_matches: list[dict]


@router.get("/{document_id}/pending-matches", response_model=PendingMatchesResponse)
def get_pending_matches(
    document_id: str,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> PendingMatchesResponse:
    """Get all pending entity matches for a document.

    Returns matches that haven't been confirmed or rejected yet.
    """
    repo = SQLAlchemyObjectRepository(db)
    doc = _load(db, repo, document_id)
    _require_read(doc, user)

    match_store = SQLEntityMatchStore(db)
    all_matches = match_store.by_source(document_id)

    # Filter to only pending or conflict (not confirmed/rejected)
    pending = [
        {
            "target_doc_id": m.target_doc_id,
            "confidence": m.confidence,
            "evidence": m.evidence,
            "decision": m.decision.value,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in all_matches
        if m.decision in (MatchDecision.PENDING, MatchDecision.CONFLICT)
    ]

    return PendingMatchesResponse(
        document_id=document_id,
        pending_matches=pending,
    )
