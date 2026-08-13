"""L5 tool-layer contracts (Freeze Contract §18).

A tool is a deterministic, ACL-gated operation over AcademicOS data. The frozen
registry fields are ``name``, ``input_schema``, ``output_schema``, ``acl_scope``,
``deterministic``, ``cost_class``. A tool carries the user's principal and is
audited (Freeze Contract §13.5.6). Stdlib-only (application layer).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolSpec:
    """The frozen tool registry entry (Freeze Contract §18)."""

    name: str
    input_schema: dict
    output_schema: dict
    acl_scope: str
    deterministic: bool = True
    cost_class: str = "local"


@dataclass(frozen=True)
class ToolInvocation:
    """One tool call request (principal-carrying)."""

    principal: str
    tool_name: str
    args: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """Deterministic structured result (or error) of one tool call."""

    tool_name: str
    principal: str
    ok: bool
    value: object | None = None
    error: str | None = None
    call_id: str = ""


@dataclass(frozen=True)
class ToolCallRecord:
    """Durable audit record of one tool call (Freeze Contract §13.5.6)."""

    call_id: str
    tool_name: str
    principal: str
    acl_scope: str
    ok: bool
    cost_class: str
    created_at: str = ""


__all__ = [
    "ToolCallRecord",
    "ToolInvocation",
    "ToolResult",
    "ToolSpec",
]
