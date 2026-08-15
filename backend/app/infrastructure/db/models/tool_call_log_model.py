"""SQLAlchemy model: ``tool_call_log`` — L5 tool-call audit (ADR-037).

Append-only, idempotent-by-``call_id``. Records tool identity, principal,
acl_scope, success, cost_class. Never stores sensitive payloads.
"""

from __future__ import annotations

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.object_model import Base, TenantStampMixin


class ToolCallLogModel(TenantStampMixin, Base):
    __tablename__ = "tool_call_log"
    __table_args__ = (
        Index("ix_tool_call_log_tool_principal", "tool_name", "principal"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    tool_name: Mapped[str] = mapped_column(String, nullable=False)
    principal: Mapped[str] = mapped_column(String, nullable=False)
    acl_scope: Mapped[str | None] = mapped_column(String, nullable=True)
    ok: Mapped[bool] = mapped_column(Integer, nullable=False)  # SQLite bool as int
    cost_class: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
