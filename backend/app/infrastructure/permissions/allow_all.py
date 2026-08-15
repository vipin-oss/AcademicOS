"""Default permission evaluator — allow everything (R4 seam).

Backward-compatible default: until a real evaluator lands (S1 auth + S2
edge ACL), every existing flow must behave exactly as before, and today
nothing is permission-gated. Consumers composed in S2/S5 swap this for a
real evaluator behind the same ``PermissionEvaluator`` port.
"""
from __future__ import annotations

from app.application.ports.permission import PermissionEvaluator
from app.domain.value_objects.enums import PermissionAction


class AllowAllPermissionEvaluator(PermissionEvaluator):
    """Permits every action for every principal in every scope."""

    def can(
        self,
        *,
        principal: dict | None,
        scope: str | None,
        action: PermissionAction,
    ) -> bool:
        return True
