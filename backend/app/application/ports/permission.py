"""Application port: permission evaluation (R4 — permission planning seam).

This is the interface where every future permission check plugs in. R4
delivers the contract only — enforcement lands in S2 (edge ACL) and S5
(search pre-filtering), per the approved roadmap.

Frozen contract (architecture docs):

- **Capability 11 (Object-Centric Blueprint):** ACL lives on the Object
  and its edges (``acl_scope``); it is *enforced at the infrastructure
  layer* — domain and application logic never decide access themselves.
- **P2 (AI Architecture):** permission is a **pre-filter, never a
  post-filter**. The retrievable set is computed from the principal's
  authorisation *before* any index is touched. Callers MUST use ``can``
  to build the allowed set up front, never to filter results afterwards.
- **Scopes are opaque strings** (e.g. ``"dept:cs"``, ``"space:…"``).
  Deciding whether a principal belongs to a scope is the evaluator's job;
  callers never parse scope syntax.

The default ``AllowAllPermissionEvaluator`` (infrastructure) preserves
today's behaviour (everything allowed) until a real evaluator exists.
"""
from __future__ import annotations

import abc

from app.domain.value_objects.enums import PermissionAction


class PermissionEvaluator(abc.ABC):
    """Decides whether a principal may perform an action within a scope."""

    @abc.abstractmethod
    def can(
        self,
        *,
        principal: dict | None,
        scope: str | None,
        action: PermissionAction,
    ) -> bool:
        """True if ``principal`` may perform ``action`` within ``scope``.

        - ``principal``: identity claims (``None`` = unauthenticated).
        - ``scope``: opaque ACL scope string (``None`` = unscoped / public).
        - ``action``: ``PermissionAction`` (READ / WRITE / MANAGE).

        Pre-filter contract (P2): callers compute the allowed set with this
        method before touching any store; they never post-filter results.
        """
