"""Admin panel surface (V3 M14, ADR-061).

Read-only operational views for the admin panel (users, roles, job queue,
spend, storage, extraction health). Every endpoint is MANAGE-gated
(admin-only). User/role management already exists on `/auth` (list_users +
assign_user_roles); this router adds the operational aggregates the blueprint's
admin panel needs.

Frontend (role-aware navigation, UX states) is deferred — this ships the
backend contract the panel consumes.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_permission
from app.application.services.extraction_health import ExtractionHealthService
from app.application.services.tenant_service import TenantService
from app.domain.value_objects.enums import PermissionAction
from app.infrastructure.db.session import get_db
from app.infrastructure.persistence.claim_decision_store import SQLClaimDecisionStore
from app.infrastructure.persistence.claim_store import SQLClaimStore
from app.infrastructure.persistence.tenant_store import SQLTenantStore

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_permission(PermissionAction.MANAGE))],
)


class JobQueueOut(BaseModel):
    pending: int
    running: int
    retryable: int
    failed: int
    succeeded: int


class SpendOut(BaseModel):
    total_usd: float
    by_user: dict[str, float]


class StorageOut(BaseModel):
    total_bytes: int
    file_count: int


@router.get("/jobs", response_model=JobQueueOut)
def admin_jobs(db: Session = Depends(get_db)) -> JobQueueOut:
    def count(status: str) -> int:
        return db.execute(
            text("SELECT COUNT(*) FROM jobs WHERE status = :s"), {"s": status}
        ).scalar()

    return JobQueueOut(
        pending=count("pending"),
        running=count("running"),
        retryable=count("retryable"),
        failed=count("failed"),
        succeeded=count("succeeded"),
    )


@router.get("/spend", response_model=SpendOut)
def admin_spend(db: Session = Depends(get_db)) -> SpendOut:
    total = db.execute(text("SELECT COALESCE(SUM(estimated_cost_usd), 0) FROM spend_ledger")).scalar()
    by_user_rows = db.execute(
        text("SELECT user_id, SUM(estimated_cost_usd) FROM spend_ledger GROUP BY user_id")
    ).fetchall()
    return SpendOut(
        total_usd=float(total or 0.0),
        by_user={str(u): float(s or 0.0) for u, s in by_user_rows},
    )


@router.get("/storage", response_model=StorageOut)
def admin_storage(
    db: Session = Depends(get_db),
) -> StorageOut:
    total_bytes = 0
    file_count = 0
    root = Path("storage")
    if root.exists():
        for p in root.rglob("*"):
            if p.is_file():
                total_bytes += p.stat().st_size
                file_count += 1
    return StorageOut(total_bytes=total_bytes, file_count=file_count)


@router.get("/extraction-health")
def admin_extraction_health(db: Session = Depends(get_db)) -> dict:
    health = ExtractionHealthService(SQLClaimStore(db), SQLClaimDecisionStore(db)).health()
    return {
        "total_corrections": health.total_corrections,
        "by_predicate": health.by_predicate,
    }


# ---------------------------------------------------------------------------
# V3 M15 (ADR-062): tenant lifecycle
# ---------------------------------------------------------------------------

class TenantCreateBody(BaseModel):
    name: str
    storage_quota_bytes: int = 0
    spend_cap_usd: float = 0.0


class TenantOut(BaseModel):
    id: str
    name: str
    status: str
    storage_quota_bytes: int
    spend_cap_usd: float


class TenantMemberBody(BaseModel):
    user_id: str
    role: str = "member"


@router.get("/tenants", response_model=list[TenantOut])
def list_tenants(db: Session = Depends(get_db)) -> list[TenantOut]:
    return [TenantOut(**t.__dict__) for t in TenantService(SQLTenantStore(db)).list()]


@router.post("/tenants", response_model=TenantOut, status_code=201)
def create_tenant(body: TenantCreateBody, db: Session = Depends(get_db)) -> TenantOut:
    tenant = TenantService(SQLTenantStore(db)).create(
        name=body.name,
        storage_quota_bytes=body.storage_quota_bytes,
        spend_cap_usd=body.spend_cap_usd,
    )
    return TenantOut(**tenant.__dict__)


@router.post("/tenants/{tenant_id}/suspend", response_model=TenantOut)
def suspend_tenant(tenant_id: str, db: Session = Depends(get_db)) -> TenantOut:
    try:
        tenant = TenantService(SQLTenantStore(db)).suspend(tenant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TenantOut(**tenant.__dict__)


@router.post("/tenants/{tenant_id}/resume", response_model=TenantOut)
def resume_tenant(tenant_id: str, db: Session = Depends(get_db)) -> TenantOut:
    try:
        tenant = TenantService(SQLTenantStore(db)).resume(tenant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TenantOut(**tenant.__dict__)


@router.post("/tenants/{tenant_id}/members", status_code=201)
def add_tenant_member(
    tenant_id: str, body: TenantMemberBody, db: Session = Depends(get_db)
) -> dict:
    try:
        TenantService(SQLTenantStore(db)).add_member(
            organization_id=tenant_id, user_id=body.user_id, role=body.role
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@router.get("/tenants/{tenant_id}/members")
def list_tenant_members(tenant_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        members = TenantService(SQLTenantStore(db)).members(tenant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"members": [{"user_id": u, "role": r} for u, r in members]}
