"""L5 deterministic data tools (Freeze Contract §18, ADR-037).

Deterministic tools over the existing ``ObjectRepository``: inventory, count,
list, lookup. They wrap the repository (no new retrieval/ACL system) and return
structured results. ACL on the tool's ``acl_scope`` is enforced by the executor.
"""

from __future__ import annotations

from app.application.dtos.tool import ToolResult, ToolSpec
from app.application.ports.tool_registry import Tool
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId


class InventoryTool(Tool):
    """inventory — list what knowledge/data kinds the system holds."""

    spec = ToolSpec(
        name="inventory",
        input_schema={"properties": {"domains": {"type": "list"}}},
        output_schema={"properties": {"kinds": {"type": "list"}}},
        acl_scope="inventory",
    )

    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, *, principal: str, args: dict) -> ToolResult:
        kinds: dict[str, int] = {}
        for obj in self._repository.find():
            if obj.status is ObjectStatus.SUPERSEDED:
                continue
            kinds[obj.object_type.value] = kinds.get(obj.object_type.value, 0) + 1
        return ToolResult(
            tool_name="inventory", principal=principal, ok=True,
            value={"kinds": [{"type": t, "count": c} for t, c in sorted(kinds.items())]},
        )


class CountTool(Tool):
    """count — deterministic count of objects by type (never LLM arithmetic)."""

    spec = ToolSpec(
        name="count",
        input_schema={
            "properties": {"object_type": {"type": "string"}},
        },
        output_schema={"properties": {"count": {"type": "integer"}}},
        acl_scope="count",
    )

    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, *, principal: str, args: dict) -> ToolResult:
        object_type = args.get("object_type")
        if object_type and object_type not in ObjectType._value2member_map_:
            # A provided-but-unknown object type has no matches.
            return ToolResult(
                tool_name="count", principal=principal, ok=True, value={"count": 0}
            )
        ot = ObjectType(object_type) if object_type else None
        n = self._repository.count(object_type=ot, status=ObjectStatus.ACTIVE)
        return ToolResult(
            tool_name="count", principal=principal, ok=True, value={"count": n}
        )


class ListTool(Tool):
    """list — enumerate matching records (title + id), bounded."""

    spec = ToolSpec(
        name="list",
        input_schema={
            "properties": {"object_type": {"type": "string"}, "limit": {"type": "integer"}},
        },
        output_schema={"properties": {"items": {"type": "list"}}},
        acl_scope="list",
    )

    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, *, principal: str, args: dict) -> ToolResult:
        object_type = args.get("object_type")
        ot = ObjectType(object_type) if object_type and object_type in ObjectType._value2member_map_ else None
        limit = int(args.get("limit") or 100)
        objs = self._repository.find(object_type=ot, status=ObjectStatus.ACTIVE)
        items = [
            {"id": str(o.id), "title": o.title, "object_type": o.object_type.value}
            for o in objs[:limit]
        ]
        return ToolResult(
            tool_name="list", principal=principal, ok=True, value={"items": items}
        )


class LookupTool(Tool):
    """lookup — fetch one known record by identity/unique key."""

    spec = ToolSpec(
        name="lookup",
        input_schema={"properties": {"object_id": {"type": "string"}}},
        output_schema={"properties": {"object": {"type": "object"}}},
        acl_scope="lookup",
    )

    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, *, principal: str, args: dict) -> ToolResult:
        object_id = args.get("object_id")
        obj = self._repository.get_by_id(ObjectId(object_id)) if object_id else None
        if obj is None or obj.status is ObjectStatus.SUPERSEDED:
            return ToolResult(
                tool_name="lookup", principal=principal, ok=False,
                error="Object not found", value={"object": None},
            )
        return ToolResult(
            tool_name="lookup", principal=principal, ok=True,
            value={"object": {"id": str(obj.id), "title": obj.title,
                              "object_type": obj.object_type.value}},
        )


__all__ = ["CountTool", "InventoryTool", "ListTool", "LookupTool"]
