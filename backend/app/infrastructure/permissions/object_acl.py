"""Object-level ACL permission evaluator (Sprint-2 M1 — R4 seam).

Implements the R4 ``PermissionEvaluator`` port for a single Object. The
``scope`` argument carries the object's ACL as a JSON string:

    {"owner": "<user id>", "readers": [...], "writers": [...], "managers": [...]}

Resolution matrix (per the frozen Object-Centric capability 11 and the
SRS conflict rule "explicit ALLOW ... default DENY"):

- scope missing/malformed      -> allow everything (no ACL at all = the
                                  pre-ACL status quo; backward compatible);
- explicit grants present      -> admin role / owner / managers -> MANAGE
                                  (implies WRITE+READ); writers ->
                                  WRITE+READ; readers -> READ; else deny;
- no explicit grants (owner
  only)                        -> READ/WRITE stay open (status quo), but
                                  MANAGE (delete, ACL management) requires
                                  the owner or an admin — anyone could
                                  otherwise self-grant through the ACL
                                  endpoint.

Entries are principal ids ("obj:user:...") or "role:<name>"; a principal
matches an entry when its sub matches, or one of its roles matches
"role:<name>".
"""
from __future__ import annotations

import json

from app.application.ports.permission import PermissionEvaluator
from app.domain.value_objects.enums import PermissionAction, UserRole

_GRANT_KEYS = ("readers", "writers", "managers")


def _matches(entry: str, sub: str, roles: list[str]) -> bool:
    if entry == sub:
        return True
    if entry.startswith("role:") and entry[len("role:"):] in roles:
        return True
    return False


class ObjectPermissionEvaluator(PermissionEvaluator):
    """Decides READ/WRITE/MANAGE on one Object from its ACL metadata.

    V3 M9 (ADR-056): ``deny_by_default`` flips the two fail-open legacy cases
    to fail-closed. It defaults to the configured security posture and may be
    overridden per-instance (tests). When ON:

    - missing / malformed ACL  -> deny (never "the pre-ACL status quo");
    - owner-only ACL            -> owner + admin only (never "READ/WRITE open");
    - explicit grants           -> unchanged (explicit ALLOW still wins).

    Security rollback must NEVER restore fail-open: the flag only ever moves
    fail-open -> fail-closed.
    """

    def __init__(self, *, deny_by_default: bool | None = None) -> None:
        if deny_by_default is None:
            from app.core.config import settings

            deny_by_default = settings.security_deny_by_default
        self._deny_by_default = deny_by_default

    def can(
        self,
        *,
        principal: dict | None,
        scope: str | None,
        action: PermissionAction,
    ) -> bool:
        if principal is None:
            return False
        sub = str(principal.get("sub") or "")
        roles = [str(r) for r in (principal.get("roles") or [])]

        acl = _decode(scope)
        if acl is None:
            # No ACL metadata at all.
            return not self._deny_by_default

        owner = str(acl.get("owner") or "")
        grants_present = any(acl.get(k) for k in _GRANT_KEYS)

        if not grants_present:
            # Owner-only ACL.
            if self._deny_by_default:
                return UserRole.ADMIN.value in roles or owner == sub
            # Legacy: READ/WRITE stay open; MANAGE is ownership-gated so the
            # ACL endpoint cannot be abused to self-grant.
            if action is PermissionAction.MANAGE:
                return UserRole.ADMIN.value in roles or owner == sub
            return True

        if UserRole.ADMIN.value in roles:
            return True
        if owner == sub:
            return True
        if _any_match(acl.get("managers"), sub, roles):
            # MANAGE implies WRITE and READ.
            return True
        if action in (PermissionAction.WRITE, PermissionAction.READ) and _any_match(
            acl.get("writers"), sub, roles
        ):
            return True
        if action is PermissionAction.READ and _any_match(acl.get("readers"), sub, roles):
            return True
        return False


def _decode(scope: str | None) -> dict | None:
    if not scope:
        return None
    try:
        acl = json.loads(scope)
    except (ValueError, TypeError):
        return None
    if not isinstance(acl, dict):
        return None
    return acl


def _any_match(entries, sub: str, roles: list[str]) -> bool:
    for entry in entries or []:
        if _matches(str(entry), sub, roles):
            return True
    return False
