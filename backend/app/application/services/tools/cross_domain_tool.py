"""L8 `cross-domain` tool (Freeze Contract §18; ADR-043/ADR-037).

Deterministic entity-anchored multi-hop over the existing graph runtime. Delegates
to ``CrossDomainService`` (which reuses ``GraphRuntimeService`` + ``ObjectRepository``
+ ``PermissionEvaluator``) and returns a bounded, deterministically ordered set of
cross-domain nodes. ACL is enforced at every hop inside the service; the executor
additionally gates the tool's ``acl_scope``.

Memory is never evidence (ADR-015); this tool produces structured intermediate
results for downstream L6 citation assembly, not fabricated citations.
"""

from __future__ import annotations

from app.application.dtos.tool import ToolResult, ToolSpec
from app.application.ports.tool_registry import Tool
from app.application.services.cross_domain import CrossDomainService, resolve_user
from app.domain.repositories.object_repository import ObjectRepository


class CrossDomainTool(Tool):
    """cross-domain — entity-anchored multi-hop completion (bounded)."""

    spec = ToolSpec(
        name="cross-domain",
        input_schema={
            "properties": {
                "entities": {"type": "list"},
                "depth": {"type": "integer"},
            }
        },
        output_schema={"properties": {"nodes": {"type": "list"}, "total_count": {"type": "integer"}}},
        acl_scope="cross-domain",
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
                tool_name="cross-domain", principal=principal, ok=False,
                error=f"Unknown principal: {principal}",
            )
        entities = [str(e) for e in (args.get("entities") or [])][:20]
        if not entities:
            return ToolResult(
                tool_name="cross-domain", principal=principal, ok=False,
                error="entities required",
            )
        try:
            depth = int(args.get("depth") or 3)
        except (TypeError, ValueError):
            depth = 3
        result = self._service.multi_hop(entities, user, max_depth=depth)
        return ToolResult(
            tool_name="cross-domain", principal=principal, ok=True,
            value={
                "nodes": [
                    {
                        "object_id": n.object_id,
                        "object_type": n.object_type,
                        "title": n.title,
                        "relationship_kind": n.relationship_kind,
                        "level": n.level,
                        "path": list(n.path),
                    }
                    for n in result.nodes
                ],
                "total_count": result.total_count,
                "truncated": result.truncated,
            },
        )


__all__ = ["CrossDomainTool"]
