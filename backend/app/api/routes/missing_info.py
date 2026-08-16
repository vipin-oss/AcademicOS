"""Missing Information API — identifies incomplete academic records.

Surface:
    GET /missing-info    list missing fields across the user's records

Returns actionable items showing which records have important missing fields,
why they matter, and how to fix them.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.application.services.missing_info import MissingItem, analyze_missing_fields
from app.application.use_cases.auth.helpers import get_roles
from app.domain.entities.object import UniversalObject
from app.infrastructure.db.session import get_db
from app.infrastructure.persistence.claim_store import SQLClaimStore

router = APIRouter(
    prefix="/missing-info",
    tags=["missing-info"],
    dependencies=[Depends(get_current_user)],
)


class MissingItemOut(BaseModel):
    record_id: str
    record_type: str
    record_title: str
    missing_field: str
    predicate_id: str
    why_it_matters: str
    source_document_id: str | None = None


@router.get("", response_model=list[MissingItemOut])
def get_missing_info(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> list[MissingItemOut]:
    """List important missing fields across the user's academic records."""
    store = SQLClaimStore(db)
    items = analyze_missing_fields(store, str(user.id))
    return [
        MissingItemOut(
            record_id=m.record_id,
            record_type=m.record_type,
            record_title=m.record_title,
            missing_field=m.missing_field,
            predicate_id=m.predicate_id,
            why_it_matters=m.why_it_matters,
            source_document_id=m.source_document_id,
        )
        for m in items[:limit]
    ]
