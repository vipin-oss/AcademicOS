"""SQL implementation of the L5 tool-call audit store (ADR-037)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.dtos.tool import ToolCallRecord
from app.application.ports.tool_audit_store import ToolAuditStore
from app.infrastructure.db.models.tool_call_log_model import ToolCallLogModel


class SQLToolAuditStore(ToolAuditStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: ToolCallRecord) -> ToolCallRecord:
        existing = self._session.execute(
            select(ToolCallLogModel).where(
                ToolCallLogModel.call_id == record.call_id
            )
        ).scalars().first()
        if existing is not None:
            return record  # idempotent
        self._session.add(
            ToolCallLogModel(
                call_id=record.call_id,
                tool_name=record.tool_name,
                principal=record.principal,
                acl_scope=record.acl_scope,
                ok=int(record.ok),
                cost_class=record.cost_class,
                created_at=record.created_at,
            )
        )
        return record

    def recent(self, limit: int = 50) -> list[ToolCallRecord]:
        rows = self._session.execute(
            select(ToolCallLogModel)
            .order_by(ToolCallLogModel.created_at.desc(), ToolCallLogModel.id.desc())
            .limit(limit)
        ).scalars().all()
        return [
            ToolCallRecord(
                call_id=r.call_id, tool_name=r.tool_name, principal=r.principal,
                acl_scope=r.acl_scope, ok=bool(r.ok), cost_class=r.cost_class,
                created_at=r.created_at,
            )
            for r in rows
        ]
