"""L8 `compare` tool (Freeze Contract §18; ADR-043/ADR-037).

Deterministic comparison over authorized retrieved results, preserving
source/evidence linkage, defining missing-value behavior, deterministic
ordering, and no hallucinated values. Delegates to ``CrossDomainService.compare``.
Structured output is suitable for L6 citation assembly.
"""

from __future__ import annotations

from app.application.dtos.tool import ToolResult, ToolSpec
from app.application.ports.tool_registry import Tool
from app.application.services.cross_domain import CrossDomainService, resolve_user
from app.domain.repositories.object_repository import ObjectRepository


class CompareTool(Tool):
    """compare — deterministic contrast over authorized results."""

    spec = ToolSpec(
        name="compare",
        input_schema={
            "properties": {
                "labels": {"type": "list"},
                "object_type": {"type": "string"},
                "metadata_key": {"type": "string"},
            }
        },
        output_schema={
            "properties": {
                "rows": {"type": "list"},
                "total": {"type": "integer"},
            }
        },
        acl_scope="compare",
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
                tool_name="compare", principal=principal, ok=False,
                error=f"Unknown principal: {principal}",
            )
        labels = [str(l) for l in (args.get("labels") or [])][:20]
        if not labels:
            return ToolResult(
                tool_name="compare", principal=principal, ok=False,
                error="labels required",
            )
        result = self._service.compare(
            labels=labels,
            user=user,
            metadata_key=args.get("metadata_key"),
            target_type=args.get("object_type"),
        )
        return ToolResult(
            tool_name="compare", principal=principal, ok=True,
            value={
                "rows": [
                    {
                        "label": r.label,
                        "object_id": r.object_id,
                        "object_type": r.object_type,
                        "value": r.value,
                        "missing": r.missing,
                        "source_ids": list(r.source_ids),
                    }
                    for r in result.rows
                ],
                "total": result.total,
            },
        )


__all__ = ["CompareTool"]
