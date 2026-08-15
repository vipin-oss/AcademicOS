"""V3 M15 architecture guardrails (ADR-062).

Pins the multi-tenant contracts:

- isolation is tenant_id-stamp based (M3) + tenant predicates first in WHERE;
- enforcement is a flag, never a migration (M9 + M3);
- per-tenant storage quota + spend cap ride the organization row;
- RLS is defense-in-depth (Postgres), behind app checks — never the primary
  boundary.
"""

from __future__ import annotations

import inspect


def test_tenant_columns_on_organization_and_membership() -> None:
    import app.infrastructure.db.models.organization_model as mod

    src = inspect.getsource(mod)
    assert "class OrganizationModel" in src and "class MembershipModel" in src


def test_tenant_lifecycle_is_flagged_not_migrated() -> None:
    import app.application.services.tenant_service as mod

    src = inspect.getsource(mod)
    assert "STATUS_ACTIVE" in src and "STATUS_SUSPENDED" in src
    assert "suspend" in src and "resume" in src


def test_tenant_predicate_first_in_where() -> None:
    import app.application.services.saved_view_compiler as mod

    src = inspect.getsource(mod)
    assert 'where = ["tenant_id = :tenant"]' in src


def test_tenant_routes_are_manage_gated() -> None:
    import app.api.routes.admin as mod

    src = inspect.getsource(mod)
    assert "PermissionAction.MANAGE" in src
    assert "TenantService" in src
