"""Confirmation inbox API (L1, ADR-004 / ADR-006 / ADR-022).

A thin read surface over the claim store exposing the human-confirmation
queue: proposed (candidate) claims that are not yet canonical. Promoting /
rejecting happens through the claims routes (``/claims/{id}/confirm|reject``);
this route keeps the "extracted candidate vs confirmed canonical knowledge"
distinction visible as an inbox (ADR-010 of the product pipeline).

OpenAPI contract surface (ADR-022): the frontend/L3 UI consumes only this and
the claims contract.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.domain.value_objects.claim import ClaimStatus
from app.infrastructure.db.session import get_db
from app.infrastructure.persistence.claim_store import SQLClaimStore

router = APIRouter(
    prefix="/confirmations",
    tags=["confirmations"],
    dependencies=[Depends(get_current_user)],
)


class PendingClaimOut(BaseModel):
    claim_id: str
    predicate_id: str
    source_document_id: str
    source_version: int
    value_schema: str
    status: str


@router.get("/pending", response_model=list[PendingClaimOut])
def pending_claims(db: Session = Depends(get_db)) -> list[PendingClaimOut]:
    claims = SQLClaimStore(db).by_status(ClaimStatus.PROPOSED)
    return [
        PendingClaimOut(
            claim_id=c.claim_id,
            predicate_id=c.predicate_id,
            source_document_id=c.source_document_id,
            source_version=c.source_version,
            value_schema=c.value_schema,
            status=c.status.value,
        )
        for c in claims
    ]
