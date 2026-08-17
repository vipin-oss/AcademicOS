"""Confirmation API (L3, ADR-022 / ADR-032 / ADR-033).

Human-in-the-loop confirmation/correction over the L1 claim plane:
  - GET /confirmations/pending        triaged, ACL-filtered, paginated queue
  - POST /confirmations/{claim_id}/approve
  - POST /confirmations/{claim_id}/reject
  - POST /confirmations/{claim_id}/correct   (new ASSERTED supersedes candidate)
  - GET  /confirmations/{claim_id}/decisions  audit history
  - POST /confirmations/cdm/{block_id}/approve|reject   (CDM-block decisions)

Every action writes a durable, attributable decision row (ADR-032) and is
ACL-gated: the reviewer must hold WRITE/MANAGE on the source document's scope
(``require_object_access``). Candidates outside the reviewer's scopes are never
returned (no cross-scope leakage, ADR-033).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.application.services.bulk_confirmation import (
    BULK_CONFIRM_MIN_CONFIDENCE,
    BulkConfirmationService,
)
from app.application.services.cdm_confirmation import CdmConfirmationService
from app.application.services.claim_confirmation import ClaimConfirmationService
from app.application.services.confirmation_queue import ConfirmationQueue
from app.application.services.extraction_health import (
    ConflictReport,
    ExtractionHealthService,
)
from app.domain.entities.object import UniversalObject
from app.infrastructure.db.session import get_db
from app.infrastructure.persistence.cdm_decision_store import SQLCdmDecisionStore
from app.infrastructure.persistence.claim_decision_store import SQLClaimDecisionStore
from app.infrastructure.persistence.claim_store import SQLClaimStore
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

router = APIRouter(
    prefix="/confirmations",
    tags=["confirmations"],
    dependencies=[Depends(get_current_user)],
)


class PendingOut(BaseModel):
    claim_id: str
    predicate_id: str
    value_schema: str
    source_document_id: str
    source_version: int
    fact_confidence: float | None
    extraction_confidence: float | None
    acl_scope: str | None
    tier: str
    display_value: str = ""
    source_text: str = ""
    document_title: str = ""


class DecisionOut(BaseModel):
    decision_id: str
    subject_id: str
    decision: str
    reviewer: str
    previous_status: str
    resulting_status: str
    notes: str
    acl_scope: str | None
    eval_run_id: str | None
    created_at: str


class CorrectBody(BaseModel):
    raw_value: Any = None
    source_text: str = ""
    notes: str = Field(default="", max_length=1000)


def _claim_confirm_service(db: Session) -> ClaimConfirmationService:
    from app.application.services.claim_service import ClaimService

    return ClaimConfirmationService(
        ClaimService(SQLClaimStore(db)), SQLClaimDecisionStore(db)
    )


def _cdm_confirm_service(db: Session) -> CdmConfirmationService:
    return CdmConfirmationService(SQLCdmDecisionStore(db))


def _can_decide(user: UniversalObject) -> Callable[[str | None], bool]:
    """A predicate: can this reviewer decide on a candidate with acl_scope?"""
    from app.application.services.confirmation_acl import reviewer_can_decide

    reviewer = str(user.id)
    return lambda scope: reviewer_can_decide(scope, reviewer)


@router.get("/pending", response_model=list[PendingOut])
def pending(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    needs_ocr_only: bool = Query(False),
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> list[PendingOut]:
    """Triaged, ACL-filtered, paginated PROPOSED claim candidates."""
    queue = ConfirmationQueue(SQLClaimStore(db))
    items = queue.pending(
        page=page, page_size=page_size, can_decide=_can_decide(user),
    )

    # Batch-load document titles for all unique source_document_ids
    from app.domain.value_objects.object_id import ObjectId
    from app.domain.value_objects.enums import ObjectType
    repo = SQLAlchemyObjectRepository(db)
    doc_ids = {i.source_document_id for i in items if i.source_document_id}
    doc_titles: dict[str, str] = {}
    for did in doc_ids:
        try:
            doc = repo.get_by_id(ObjectId(did))
            if doc is not None and doc.object_type is ObjectType.DOCUMENT:
                doc_titles[did] = doc.title or did
        except Exception:  # noqa: BLE001 - best-effort title lookup
            pass

    return [
        PendingOut(
            claim_id=i.claim_id, predicate_id=i.predicate_id,
            value_schema=i.value_schema, source_document_id=i.source_document_id,
            source_version=i.source_version, fact_confidence=i.fact_confidence,
            extraction_confidence=i.extraction_confidence, acl_scope=i.acl_scope,
            tier=i.tier,
            display_value=i.display_value,
            source_text=i.source_text,
            document_title=doc_titles.get(i.source_document_id, ""),
        )
        for i in items
    ]


@router.post("/{claim_id}/approve", response_model=DecisionOut)
def approve_claim(
    claim_id: str,
    notes: str = Query(default="", max_length=1000),
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> DecisionOut:
    try:
        record = _claim_confirm_service(db).approve(
            claim_id, reviewer=str(user.id), notes=notes
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    db.commit()
    return _to_decision(record)


@router.post("/{claim_id}/reject", response_model=DecisionOut)
def reject_claim(
    claim_id: str,
    notes: str = Query(default="", max_length=1000),
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> DecisionOut:
    try:
        record = _claim_confirm_service(db).reject(
            claim_id, reviewer=str(user.id), notes=notes
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.commit()
    return _to_decision(record)


@router.post("/{claim_id}/correct", response_model=DecisionOut)
def correct_claim(
    claim_id: str,
    body: CorrectBody,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> DecisionOut:
    try:
        record = _claim_confirm_service(db).correct(
            claim_id, reviewer=str(user.id), raw_value=body.raw_value,
            source_text=body.source_text, notes=body.notes,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.commit()
    return _to_decision(record)


@router.get("/{claim_id}/decisions", response_model=list[DecisionOut])
def claim_decisions(
    claim_id: str,
    db: Session = Depends(get_db),
) -> list[DecisionOut]:
    records = SQLClaimDecisionStore(db).by_claim(claim_id)
    return [_to_decision(r) for r in records]


class BulkConfirmOut(BaseModel):
    confirmed: int
    skipped: int
    decisions: list[DecisionOut]


@router.post("/suggested/confirm-all", response_model=BulkConfirmOut)
def bulk_confirm_suggested(
    min_confidence: float = Query(
        default=BULK_CONFIRM_MIN_CONFIDENCE, ge=0.0, le=1.0,
        description="Minimum fact_confidence for a suggested claim to be bulk-confirmed.",
    ),
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> BulkConfirmOut:
    """Bulk human confirmation of AUTO_SUGGESTED claims (V3 M7, ADR-054).

    Confirms every suggested claim at/above ``min_confidence`` that the
    reviewer is allowed to decide on, in one transaction. Every confirmation
    is a separate durable, attributable decision row (never auto-approval);
    the batch is atomic (a failure rolls the whole run back) and undoable
    through the existing reject/correct endpoints.
    """
    service = BulkConfirmationService(
        SQLClaimStore(db), SQLClaimDecisionStore(db)
    )
    result = service.confirm_suggested(
        reviewer=str(user.id),
        min_confidence=min_confidence,
        can_decide=_can_decide(user),
    )
    db.commit()
    return BulkConfirmOut(
        confirmed=result.confirmed,
        skipped=result.skipped,
        decisions=[_to_decision(d) for d in result.decisions],
    )


class HealthOut(BaseModel):
    total_corrections: int
    by_predicate: dict[str, int]
    conflicts: list[dict]


@router.get("/health", response_model=HealthOut)
def extraction_health(
    db: Session = Depends(get_db),
) -> HealthOut:
    """Extraction health + conflict escalation (V3 M7, ADR-054).

    Aggregates the ``correct`` decision trail into per-predicate correction
    counts and surfaces value conflicts between non-authoritative candidates
    and CONFIRMED facts (both sides shown; never auto-resolved).
    """
    health = ExtractionHealthService(
        SQLClaimStore(db), SQLClaimDecisionStore(db)
    ).health()
    conflicts = ConflictReport(SQLClaimStore(db)).conflicts()
    return HealthOut(
        total_corrections=health.total_corrections,
        by_predicate=health.by_predicate,
        conflicts=[
            {
                "predicate_id": c.predicate_id,
                "confirmed_claim_id": c.confirmed_claim_id,
                "confirmed_value": c.confirmed_value,
                "candidate_claim_id": c.candidate_claim_id,
                "candidate_value": c.candidate_value,
                "candidate_status": c.candidate_status,
            }
            for c in conflicts
        ],
    )


@router.post("/cdm/{block_id}/approve", response_model=DecisionOut)
def approve_cdm(
    block_id: str,
    notes: str = Query(default="", max_length=1000),
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> DecisionOut:
    record = _cdm_confirm_service(db).approve(
        block_id, reviewer=str(user.id), notes=notes
    )
    return _to_decision(record)


@router.post("/cdm/{block_id}/reject", response_model=DecisionOut)
def reject_cdm(
    block_id: str,
    notes: str = Query(default="", max_length=1000),
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> DecisionOut:
    record = _cdm_confirm_service(db).reject(
        block_id, reviewer=str(user.id), notes=notes
    )
    return _to_decision(record)


def _to_decision(r) -> DecisionOut:
    return DecisionOut(
        decision_id=r.decision_id, subject_id=r.subject_id, decision=r.decision,
        reviewer=r.reviewer, previous_status=r.previous_status,
        resulting_status=r.resulting_status, notes=r.notes, acl_scope=r.acl_scope,
        eval_run_id=r.eval_run_id, created_at=r.created_at,
    )
