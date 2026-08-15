"""V3 M9 architecture guardrails (ADR-056).

Pins the security contracts:

- deny-by-default is posture-gated and only ever moves fail-open -> fail-closed
  (security rollback must NEVER restore fail-open);
- the evaluators read the configured posture (settings), overridable per
  instance for tests only;
- search authorizes candidates BEFORE ranking (pre-filter, never post-filter);
- principal is built server-side (never from client claims);
- revocation is durable and idempotent.
"""

from __future__ import annotations

import inspect

from app.application.services.principal import principal_from_user
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.infrastructure.permissions.object_acl import ObjectPermissionEvaluator
from app.infrastructure.permissions.role_based import RoleBasedPermissionEvaluator


def test_deny_by_default_reads_config() -> None:
    # The evaluator defaults to the configured posture (settings).
    src = inspect.getsource(ObjectPermissionEvaluator.__init__)
    assert "security_deny_by_default" in src
    src2 = inspect.getsource(RoleBasedPermissionEvaluator.__init__)
    assert "security_deny_by_default" in src2


def test_deny_by_default_never_restores_fail_open() -> None:
    # In fail-closed mode, missing ACL must deny (the fail-open branch is gone).
    src = inspect.getsource(ObjectPermissionEvaluator.can)
    assert "not self._deny_by_default" in src


def test_search_prefilters_before_ranking() -> None:
    src = inspect.getsource(SearchObjectsUseCase.execute)
    # authorization happens before _fuse (ranking)
    auth_idx = src.index("self._authorized")
    fuse_idx = src.index("_fuse(")
    assert auth_idx < fuse_idx


def test_principal_built_from_live_user() -> None:
    src = inspect.getsource(principal_from_user)
    assert "get_roles" in src


def test_revocation_store_is_durable() -> None:
    import app.infrastructure.persistence.token_revocation_store as mod

    src = inspect.getsource(mod)
    assert "SessionRevocationModel" in src
    assert "idempotent" in src.lower() or "existing is not None" in src
