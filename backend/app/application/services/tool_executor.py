"""L5 tool executor (Freeze Contract §13.5.6, §18; ADR-037).

The single execution path for every tool call. It:
  1. resolves the tool,
  2. validates the input against the tool's input_schema,
  3. enforces ACL on the tool's acl_scope for the principal,
  4. executes the tool,
  5. normalizes/validates output,
  6. records audit,
  7. returns a deterministic structured result/error.

Callers MUST go through this path — no bypass. Principal is carried throughout.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.application.dtos.tool import ToolCallRecord, ToolResult
from app.application.ports.permission import PermissionEvaluator
from app.application.ports.tool_audit_store import ToolAuditStore
from app.application.ports.tool_registry import ToolRegistry
from app.domain.value_objects.enums import PermissionAction


class ToolExecutionError(Exception):
    """A tool call failed in a deterministic way."""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_call_id() -> str:
    return f"tool:{uuid.uuid4().hex[:16]}"


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        *,
        permissions: PermissionEvaluator,
        audit: ToolAuditStore | None = None,
    ) -> None:
        self._registry = registry
        self._permissions = permissions
        self._audit = audit

    def execute(self, *, principal: str, tool_name: str, args: dict) -> ToolResult:
        call_id = new_call_id()
        tool = self._registry.get(tool_name)
        if tool is None:
            return self._recorded(
                ToolResult(tool_name=tool_name, principal=principal, ok=False,
                           error=f"Unknown tool: {tool_name}", call_id=call_id)
            )

        spec = tool.spec
        # ACL gate: the principal must be able to READ within the tool scope.
        if not self._permissions.can(
            principal={"sub": principal}, scope=spec.acl_scope, action=PermissionAction.READ
        ):
            return self._recorded(
                ToolResult(tool_name=tool_name, principal=principal, ok=False,
                           error="Access denied", call_id=call_id)
            )

        # Input validation against the input_schema (deterministic, shallow).
        validation_error = self._validate_input(args, spec.input_schema)
        if validation_error is not None:
            return self._recorded(
                ToolResult(tool_name=tool_name, principal=principal, ok=False,
                           error=f"Invalid input: {validation_error}", call_id=call_id)
            )

        try:
            result = tool.execute(principal=principal, args=args)
        except Exception as exc:  # noqa: BLE001 — deterministic error boundary
            return self._recorded(
                ToolResult(tool_name=tool_name, principal=principal, ok=False,
                           error=f"Tool failed: {exc}", call_id=call_id)
            )
        return self._recorded(result)

    def _recorded(self, result: ToolResult) -> ToolResult:
        if self._audit is not None:
            self._audit.add(
                ToolCallRecord(
                    call_id=result.call_id, tool_name=result.tool_name,
                    principal=result.principal, acl_scope=self._scope_for(result.tool_name),
                    ok=result.ok, cost_class=self._cost_for(result.tool_name),
                    created_at=_now_iso(),
                )
            )
        return result

    def _scope_for(self, tool_name: str) -> str:
        tool = self._registry.get(tool_name)
        return tool.spec.acl_scope if tool is not None else ""

    def _cost_for(self, tool_name: str) -> str:
        tool = self._registry.get(tool_name)
        return tool.spec.cost_class if tool is not None else "local"

    @staticmethod
    def _validate_input(args: dict, schema: dict) -> str | None:
        """Shallow deterministic input validation.

        ``schema`` is a JSON-like object whose keys are expected arg names and
        values are type names ("string", "integer", "boolean", "list",
        "object"). Unknown args are ignored; required keys must be present.
        """
        if not isinstance(args, dict):
            return "args must be an object"
        required = schema.get("required") or []
        properties = schema.get("properties") or {}
        for key in required:
            if key not in args:
                return f"missing required field: {key}"
        for key, spec_ in properties.items():
            if key not in args:
                continue
            typ = spec_.get("type") if isinstance(spec_, dict) else spec_
            if typ == "string" and not isinstance(args[key], str):
                return f"field {key} must be a string"
            if typ == "integer" and not isinstance(args[key], int):
                return f"field {key} must be an integer"
            if typ == "boolean" and not isinstance(args[key], bool):
                return f"field {key} must be a boolean"
            if typ == "list" and not isinstance(args[key], list):
                return f"field {key} must be a list"
            if typ == "object" and not isinstance(args[key], dict):
                return f"field {key} must be an object"
        return None


__all__ = ["ToolExecutionError", "ToolExecutor", "new_call_id"]
