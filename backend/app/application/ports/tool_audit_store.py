"""L5 tool-call audit store port (Freeze Contract §13.5.6, ADR-037).

Append-only, idempotent-by-``call_id``. Every tool call is logged for audit
(tool identity, principal, acl_scope, ok, cost_class). Sensitive payloads are
NOT stored.
"""

from __future__ import annotations

import abc

from app.application.dtos.tool import ToolCallRecord


class ToolAuditStore(abc.ABC):
    @abc.abstractmethod
    def add(self, record: ToolCallRecord) -> ToolCallRecord:
        """Append one immutable audit row (idempotent by call_id)."""

    @abc.abstractmethod
    def recent(self, limit: int = 50) -> list[ToolCallRecord]:
        """Most recent tool calls, newest first (bounded)."""
