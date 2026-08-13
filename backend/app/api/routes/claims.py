"""Claims API (L1, ADR-002 / ADR-019 / ADR-022 — OpenAPI contract surface).

Surfaces the L1 claim store:
  - GET   /claims?status=&source_document_id=   list claims
  - GET   /claims/{claim_id}                     one claim + its spans
  - POST  /claims                                propose a claim (engines)
  - POST  /claims/{claim_id}/confirm             human confirmation -> canonical
  - POST  /claims/{claim_id}/reject              human rejection
  - POST  /claims/{claim_id}/supersede           supersede by another claim

Facts vs metadata: engines propose claims HERE; they never write object
metadata directly (ADR-002). The predicate catalogue is the validator
(ADR-019); unknown/unparseable values are stored as ``raw`` + source text.
Only CONFIRMED/ASSERTED claims are auto-usable (ADR-006).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.application.services.claim_service import ClaimService
from app.domain.value_objects.claim import ClaimStatus
from app.domain.value_objects.enums import Provenance
from app.domain.value_objects.span import Span, SpanKind
from app.infrastructure.db.session import get_db
from app.infrastructure.persistence.claim_store import SQLClaimStore

router = APIRouter(
    prefix="/claims",
    tags=["claims"],
    dependencies=[Depends(get_current_user)],
)


def _store(db: Session) -> ClaimService:
    return ClaimService(SQLClaimStore(db))


class SpanIn(BaseModel):
    kind: str
    source_id: str
    page: int | None = None
    block_id: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    row_idx: int | None = None
    col_idx: int | None = None
    table_id: str | None = None
    slide: int | None = None
    bbox: list[float] | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ClaimIn(BaseModel):
    predicate_id: str
    raw_value: Any = None
    source_text: str = ""
    source_document_id: str
    source_version: int = 1
    spans: list[SpanIn] = Field(default_factory=list)
    acl_scope: str | None = None
    fact_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    provenance: str = "inferred"
    ocr_derived: bool = False


class ClaimOut(BaseModel):
    claim_id: str
    predicate_id: str
    predicate_version: int
    value_schema: str
    value: dict[str, Any]
    source_document_id: str
    source_version: int
    status: str
    provenance: str
    fact_confidence: float | None
    extraction_confidence: float | None
    acl_scope: str | None
    supersedes_claim_id: str | None
    spans: list[dict[str, Any]]


def _to_out(claim, spans: list[Span]) -> ClaimOut:
    return ClaimOut(
        claim_id=claim.claim_id,
        predicate_id=claim.predicate_id,
        predicate_version=claim.predicate_version,
        value_schema=claim.value_schema,
        value=claim.value,
        source_document_id=claim.source_document_id,
        source_version=claim.source_version,
        status=claim.status.value,
        provenance=claim.provenance.value,
        fact_confidence=claim.fact_confidence,
        extraction_confidence=claim.extraction_confidence,
        acl_scope=claim.acl_scope,
        supersedes_claim_id=claim.supersedes_claim_id,
        spans=[s.to_region_dict() for s in spans],
    )


@router.get("", response_model=list[ClaimOut])
def list_claims(
    status: ClaimStatus | None = Query(default=None),
    source_document_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ClaimOut]:
    store = _store(db)
    claims = (
        store.by_status(status) if status is not None
        else (store.by_source(source_document_id) if source_document_id else [])
    )
    out: list[ClaimOut] = []
    for c in claims:
        stored = SQLClaimStore(db).get(c.claim_id)
        _, spans = stored if stored else (c, [])
        out.append(_to_out(c, spans))
    return out


@router.get("/{claim_id}", response_model=ClaimOut)
def get_claim(claim_id: str, db: Session = Depends(get_db)) -> ClaimOut:
    stored = _store(db)._store.get(claim_id)
    if stored is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    claim, spans = stored
    return _to_out(claim, spans)


@router.post("", response_model=ClaimOut, status_code=status.HTTP_201_CREATED)
def propose_claim(body: ClaimIn, db: Session = Depends(get_db)) -> ClaimOut:
    spans = [
        Span(
            kind=SpanKind(s.kind),
            source_id=s.source_id,
            page=s.page,
            block_id=s.block_id,
            char_start=s.char_start,
            char_end=s.char_end,
            row_idx=s.row_idx,
            col_idx=s.col_idx,
            table_id=s.table_id,
            slide=s.slide,
            bbox=tuple(s.bbox) if s.bbox else None,
            payload=s.payload,
        )
        for s in body.spans
    ]
    provenance = Provenance(body.provenance)
    claim = _store(db).propose(
        predicate_id=body.predicate_id,
        raw_value=body.raw_value,
        source_text=body.source_text,
        source_document_id=body.source_document_id,
        source_version=body.source_version,
        spans=spans,
        acl_scope=body.acl_scope,
        fact_confidence=body.fact_confidence,
        extraction_confidence=body.extraction_confidence,
        provenance=provenance,
        ocr_derived=body.ocr_derived,
    )
    stored = _store(db)._store.get(claim.claim_id)
    _, spans_out = stored if stored else (claim, [])
    return _to_out(claim, spans_out)


@router.post("/{claim_id}/confirm", response_model=ClaimOut)
def confirm_claim(
    claim_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> ClaimOut:
    try:
        claim = _store(db).confirm(claim_id, reviewer=str(user.id), assert_human=True)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    stored = _store(db)._store.get(claim.claim_id)
    _, spans = stored if stored else (claim, [])
    return _to_out(claim, spans)


@router.post("/{claim_id}/reject", response_model=ClaimOut)
def reject_claim(
    claim_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> ClaimOut:
    try:
        claim = _store(db).reject(claim_id, reviewer=str(user.id))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    stored = _store(db)._store.get(claim.claim_id)
    _, spans = stored if stored else (claim, [])
    return _to_out(claim, spans)


class SupersedeIn(BaseModel):
    by_claim_id: str


@router.post("/{claim_id}/supersede", response_model=ClaimOut)
def supersede_claim(
    claim_id: str,
    body: SupersedeIn,
    db: Session = Depends(get_db),
) -> ClaimOut:
    try:
        claim = _store(db).supersede_claim(claim_id, body.by_claim_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    stored = _store(db)._store.get(claim.claim_id)
    _, spans = stored if stored else (claim, [])
    return _to_out(claim, spans)
