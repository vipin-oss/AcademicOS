"""L5 Tool API (ADR-022 / ADR-037).

  GET  /tools               — the frozen tool registry catalogue
  POST /tools/{name}/invoke — execute a tool (principal-carrying, ACL-gated,
                              audited)
  GET  /tools/calls         — recent tool-call audit log (bounded)

All calls are authenticated; the executor enforces each tool's acl_scope. No
internal implementation details are exposed beyond the registry contract.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.application.services.tool_executor import ToolExecutor
from app.application.services.tools.registry import build_tool_registry
from app.domain.entities.object import UniversalObject
from app.infrastructure.db.session import get_db
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.persistence.tool_audit_store import SQLToolAuditStore
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

router = APIRouter(
    prefix="/tools",
    tags=["tools"],
    dependencies=[Depends(get_current_user)],
)


class InvokeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    args: dict = {}


class ToolOut(BaseModel):
    name: str
    input_schema: dict
    output_schema: dict
    acl_scope: str
    deterministic: bool
    cost_class: str


class ToolResultOut(BaseModel):
    tool_name: str
    ok: bool
    value: object | None = None
    error: str | None = None
    call_id: str = ""


class AuditOut(BaseModel):
    call_id: str
    tool_name: str
    principal: str
    acl_scope: str
    ok: bool
    cost_class: str


def _registry(db: Session):
    repo = SQLAlchemyObjectRepository(db)
    # L7: memory-recall tool is exposed when a persistent-memory service is
    # available (additive; the registry is backward compatible otherwise).
    from app.application.services.persistent_memory import PersistentMemoryService

    memory = PersistentMemoryService(repo, ObjectPermissionEvaluator())
    # L8: cross-domain tools are exposed through the same executor seam
    # (additive; backward compatible when not wired).
    from app.application.services.cross_domain import CrossDomainService
    from app.application.services.graph_runtime import GraphRuntimeService

    cross_domain = CrossDomainService(
        repo, GraphRuntimeService(repo, ObjectPermissionEvaluator()), ObjectPermissionEvaluator()
    )
    return build_tool_registry(repo, memory=memory, cross_domain=cross_domain)


def _executor(db: Session) -> ToolExecutor:
    return ToolExecutor(
        _registry(db),
        permissions=ObjectPermissionEvaluator(),
        audit=SQLToolAuditStore(db),
    )


@router.get("", response_model=list[ToolOut])
def list_tools(db: Session = Depends(get_db)) -> list[ToolOut]:
    registry = _registry(db)
    return [
        ToolOut(
            name=registry.get(n).spec.name,
            input_schema=registry.get(n).spec.input_schema,
            output_schema=registry.get(n).spec.output_schema,
            acl_scope=registry.get(n).spec.acl_scope,
            deterministic=registry.get(n).spec.deterministic,
            cost_class=registry.get(n).spec.cost_class,
        )
        for n in registry.names()
    ]


@router.get("/calls", response_model=list[AuditOut])
def recent_calls(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[AuditOut]:
    records = SQLToolAuditStore(db).recent(limit)
    return [
        AuditOut(
            call_id=r.call_id, tool_name=r.tool_name, principal=r.principal,
            acl_scope=r.acl_scope, ok=r.ok, cost_class=r.cost_class,
        )
        for r in records
    ]


@router.post("/{tool_name}/invoke", response_model=ToolResultOut)
def invoke_tool(
    tool_name: str,
    body: InvokeBody,
    db: Session = Depends(get_db),
    user: UniversalObject = Depends(get_current_user),
) -> ToolResultOut:
    result = _executor(db).execute(
        principal=str(user.id), tool_name=tool_name, args=body.args
    )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Tool call failed.",
        )
    return ToolResultOut(
        tool_name=result.tool_name, ok=result.ok, value=result.value,
        error=result.error, call_id=result.call_id,
    )


__all__ = ["router"]
