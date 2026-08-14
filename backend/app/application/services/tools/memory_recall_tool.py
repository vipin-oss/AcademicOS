"""L7 `memory-recall` tool (Freeze Contract §18; ADR-037/041).

A deterministic L5 tool that recalls the principal's persistent memory for a
query. It delegates to the existing ``PersistentMemoryService`` (which itself
reuses ``ObjectRepository`` + ``PermissionEvaluator``) and returns a bounded,
deterministically ordered set of memory artifacts. Memory is **context, never
evidence** (ADR-015) — the tool never feeds the L6 citation/evidence contract.

ACL: the ``ToolExecutor`` enforces the tool's ``acl_scope``; per-artifact ACL is
additionally enforced inside ``PersistentMemoryService`` for the resolved
principal (pre-filter, no leakage).

Reuses: ``Tool``/``ToolSpec``/``ToolResult``, ``PersistentMemoryService``,
``ObjectRepository``. Does NOT create a second memory store or ACL system.
"""

from __future__ import annotations

from app.application.dtos.memory import MemoryRecallResult
from app.application.dtos.tool import ToolResult, ToolSpec
from app.application.ports.tool_registry import Tool
from app.application.services.persistent_memory import PersistentMemoryService
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class MemoryRecallTool(Tool):
    """memory-recall — recall the principal's persistent memory for a query."""

    spec = ToolSpec(
        name="memory-recall",
        input_schema={"properties": {"q": {"type": "string"}, "limit": {"type": "integer"}}},
        output_schema={"properties": {"artifacts": {"type": "list"}, "count": {"type": "integer"}}},
        acl_scope="memory-recall",
        deterministic=True,
        cost_class="local",
    )

    def __init__(
        self,
        repository: ObjectRepository,
        memory: PersistentMemoryService,
    ) -> None:
        self._repository = repository
        self._memory = memory

    def execute(self, *, principal: str, args: dict) -> ToolResult:
        user = _resolve_user(self._repository, principal)
        if user is None:
            return ToolResult(
                tool_name="memory-recall", principal=principal, ok=False,
                error=f"Unknown principal: {principal}",
            )
        query = str(args.get("q") or "")
        try:
            limit = int(args.get("limit") or 10)
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 50))
        result: MemoryRecallResult = self._memory.recall(
            query, user, limit=limit
        )
        return ToolResult(
            tool_name="memory-recall", principal=principal, ok=True,
            value={
                "artifacts": [
                    {
                        "artifact_id": r.artifact_id,
                        "title": r.title,
                        "question": r.question,
                        "answer": r.answer,
                        "review_status": r.review_status,
                        "provenance": r.provenance.value,
                        "source_ids": list(r.source_ids),
                        "version": r.version,
                    }
                    for r in result.artifacts
                ],
                "count": result.count,
            },
        )


def _resolve_user(
    repository: ObjectRepository, principal: str
) -> UniversalObject | None:
    """Resolve a principal id string to a USER UniversalObject (or None).

    Principal may be an ``obj:user:...`` id or a bare ``u:...`` user key. We
    search the repository for an ACTIVE USER object whose id or title matches,
    deterministically, so tool calls with either form resolve.
    """
    wanted = principal.strip()
    if not wanted:
        return None
    for obj in repository.find_by_type(ObjectType.USER):
        if obj.status.value in ("active",):
            if str(obj.id) == wanted or obj.title == wanted or getattr(obj, "_user_key", "") == wanted:
                return obj
    return None


__all__ = ["MemoryRecallTool"]
