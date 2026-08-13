"""L6 evidence & citation API (ADR-022 / Freeze Contract §13.6).

  GET /evidence/citable?source_document_id=…&limit=…

Returns the ACL-filtered, deterministic set of citable CONFIRMED/ASSERTED
claims (fact citations) with their source spans and confidence — the L6
backend confidence/citation output contract. Additive; existing /assistant,
/claims, /tools routes are unchanged.

Security: only claims visible to the requesting principal are returned
(reuses ObjectPermissionEvaluator + object_acl_scope). No citation leakage.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.application.services.claim_evidence import ClaimEvidenceService
from app.domain.entities.object import UniversalObject
from app.infrastructure.db.session import get_db
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.persistence.claim_store import SQLClaimStore

router = APIRouter(
    prefix="/evidence",
    tags=["evidence"],
    dependencies=[Depends(get_current_user)],
)


class ConfidenceOut(BaseModel):
    fact_confidence: float | None = None
    extraction_confidence: float | None = None
    fact_tier: str | None = None
    extraction_tier: str | None = None


class FactCitationOut(BaseModel):
    number: int
    claim_id: str
    predicate_id: str
    source_document_id: str
    source_version: int
    span: dict | None = None
    value: object | None = None
    confidence: ConfidenceOut | None = None
    authoritative: bool = True


@router.get("/citable", response_model=list[FactCitationOut])
def citable_fact_citations(
    source_document_id: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> list[FactCitationOut]:
    """Citable CONFIRMED/ASSERTED claims visible to the requesting principal."""
    service = ClaimEvidenceService(
        SQLClaimStore(db), ObjectPermissionEvaluator()
    )
    citations = service.citable_claims(
        user=user, source_document_id=source_document_id, limit=limit
    )
    return [
        FactCitationOut(
            number=c.number,
            claim_id=c.claim_id,
            predicate_id=c.predicate_id,
            source_document_id=c.source_document_id,
            source_version=c.source_version,
            span=c.span,
            value=c.value,
            confidence=ConfidenceOut(
                fact_confidence=c.confidence.fact_confidence,
                extraction_confidence=c.confidence.extraction_confidence,
                fact_tier=c.confidence.fact_tier,
                extraction_tier=c.confidence.extraction_tier,
            ),
            authoritative=c.authoritative,
        )
        for c in citations
    ]


__all__ = ["router"]
