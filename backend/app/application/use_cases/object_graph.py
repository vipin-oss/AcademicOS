"""Use case: object graph traversal with permission pre-filtering (S2 M1).

The first production Object Graph capability: outbound (related) and
inbound (referenced-by) traversal over the R1 edge table, filtered by the
object-level ACL (R4 seam, P2 pre-filter). Only objects the principal may
READ are returned — traversal never leaks.
"""
from __future__ import annotations

from app.application.ports.permission import PermissionEvaluator
from app.application.use_cases.object_acl import object_acl_scope
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import PermissionAction, RelationshipKind
from app.domain.value_objects.object_id import ObjectId


class ObjectGraphUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        evaluator: PermissionEvaluator,
    ) -> None:
        self._repository = repository
        self._evaluator = evaluator

    def execute(
        self,
        object_id: ObjectId,
        *,
        direction: str,
        principal: dict | None,
        kind: RelationshipKind | None = None,
    ) -> list[dict]:
        if direction == "outgoing":
            candidates = self._repository.find_related(object_id, kind)
        elif direction == "incoming":
            candidates = self._repository.find_inbound(object_id, kind)
        else:
            raise ValueError("direction must be 'outgoing' or 'incoming'.")

        # P2 pre-filter: the allowed set is computed from the principal's
        # authorisation before results are returned — never post-filtered.
        allowed = []
        for candidate in candidates:
            target = self._repository.get_by_id(candidate)
            if target is None:
                continue  # dangling edge (deleted target)
            if self._evaluator.can(
                principal=principal,
                scope=object_acl_scope(target),
                action=PermissionAction.READ,
            ):
                allowed.append(
                    {
                        "id": str(candidate),
                        "title": target.title,
                        "object_type": target.object_type.value,
                    }
                )
        return allowed
