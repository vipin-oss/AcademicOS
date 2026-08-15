"""L8 `temporal` tool (Freeze Contract §18; ADR-043/ADR-037).

Deterministic, rules-based time-range resolution + filtering (ADR-043 Phase 5).
Delegates to ``resolve_time_range`` / ``within_range``. No calendar/event data
model, no temporal database. Returns the resolved bounded range and a
deterministic count of authorized objects whose creation falls within it.
"""

from __future__ import annotations

from app.application.dtos.tool import ToolResult, ToolSpec
from app.application.ports.tool_registry import Tool
from app.application.services.cross_domain import (
    CrossDomainService,
    principal_for,
    resolve_user,
)
from app.application.services.temporal import resolve_time_range, within_range
from app.domain.repositories.object_repository import ObjectRepository


class TemporalTool(Tool):
    """temporal — resolve a time_range and constrain results deterministically."""

    spec = ToolSpec(
        name="temporal",
        input_schema={
            "properties": {
                "time_range": {"type": "string"},
                "object_type": {"type": "string"},
                "limit": {"type": "integer"},
            }
        },
        output_schema={
            "properties": {
                "start": {"type": "string"},
                "end": {"type": "string"},
                "count": {"type": "integer"},
                "items": {"type": "list"},
            }
        },
        acl_scope="temporal",
        deterministic=True,
        cost_class="local",
    )

    def __init__(
        self,
        repository: ObjectRepository,
        service: CrossDomainService,
    ) -> None:
        self._repository = repository
        self._service = service

    def execute(self, *, principal: str, args: dict) -> ToolResult:
        user = resolve_user(self._repository, principal)
        if user is None:
            return ToolResult(
                tool_name="temporal", principal=principal, ok=False,
                error=f"Unknown principal: {principal}",
            )
        time_range = str(args.get("time_range") or "")
        start, end = resolve_time_range(time_range)
        try:
            limit = int(args.get("limit") or 50)
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 200))

        object_type = args.get("object_type")
        if object_type and object_type not in _OBJECT_TYPES:
            return ToolResult(
                tool_name="temporal", principal=principal, ok=True,
                value={"start": _iso(start), "end": _iso(end), "count": 0, "items": []},
            )
        items = []
        for obj in self._repository.find():
            if not within_range(getattr(obj.audit, "created_at", None), start, end):
                continue
            if object_type and obj.object_type.value != object_type:
                continue
            if obj.status.value in ("superseded", "archived"):
                continue
            if not self._service._can_read(obj, principal_for(user)):  # noqa: SLF001 — reuse read gate
                continue
            items.append(
                {"object_id": str(obj.id), "title": obj.title, "object_type": obj.object_type.value}
            )
            if len(items) >= limit:
                break
        items.sort(key=lambda it: (it["object_type"], it["object_id"]))
        return ToolResult(
            tool_name="temporal", principal=principal, ok=True,
            value={
                "start": _iso(start),
                "end": _iso(end),
                "count": len(items),
                "items": items,
            },
        )


def _all_types():
    from app.domain.value_objects.enums import ObjectType

    return list(ObjectType)


_OBJECT_TYPES = frozenset({t.value for t in _all_types()})


def _iso(dt) -> str:
    return dt.isoformat() if dt is not None else ""


__all__ = ["TemporalTool"]
