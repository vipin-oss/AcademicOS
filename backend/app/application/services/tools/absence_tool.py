"""L8 `absence` tool (Freeze Contract §18; ADR-043/ADR-037).

Deterministic, ACL-aware negative/anti-join style operation: absence means
absence from the authorized/searchable scope, not an absolute claim about the
real world. Delegates to ``CrossDomainService.absence``. Never leaks unauthorized
objects (the service pre-filters every candidate).
"""

from __future__ import annotations

from app.application.dtos.tool import ToolResult, ToolSpec
from app.application.ports.tool_registry import Tool
from app.application.services.cross_domain import CrossDomainService, resolve_user
from app.domain.repositories.object_repository import ObjectRepository


class AbsenceTool(Tool):
    """absence — is X absent within the authorized/searchable scope?"""

    spec = ToolSpec(
        name="absence",
        input_schema={
            "properties": {
                "object_type": {"type": "string"},
                "metadata_key": {"type": "string"},
                "metadata_value": {"type": "string"},
            }
        },
        output_schema={
            "properties": {
                "outcome": {"type": "string"},
                "authorized_count": {"type": "integer"},
                "reason": {"type": "string"},
            }
        },
        acl_scope="absence",
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
                tool_name="absence", principal=principal, ok=False,
                error=f"Unknown principal: {principal}",
            )
        result = self._service.absence(
            target_type=args.get("object_type"),
            user=user,
            metadata_key=args.get("metadata_key"),
            metadata_value=args.get("metadata_value"),
        )
        return ToolResult(
            tool_name="absence", principal=principal, ok=True,
            value={
                "outcome": result.outcome,
                "authorized_count": result.authorized_count,
                "reason": result.reason,
            },
        )


__all__ = ["AbsenceTool"]
