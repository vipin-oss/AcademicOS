"""L3 confirmation ACL helper (ADR-032).

Determines whether a reviewer may DECIDE on a claim/candidate given its
``acl_scope`` (a JSON serialization of {owner, readers, writers, managers}).
A reviewer with WRITE/MANAGE access (owner, writer, or manager) may confirm,
reject, or correct. READ-only access does not allow decisions.
"""

from __future__ import annotations

import json


def reviewer_can_decide(acl_scope: str | None, reviewer: str) -> bool:
    """True when ``reviewer`` has WRITE/MANAGE on the scope (owner/writer/manager).

    Legacy no-ACL claims (``acl_scope is None``) are OPEN by default (the
    repository's legacy no-ACL semantics), so they are visible/decidable.
    """
    if not acl_scope:
        return True  # legacy open-by-default (Freeze Contract ADR-017 note)
    try:
        acl = json.loads(acl_scope)
    except (ValueError, TypeError):
        return False
    owner = acl.get("owner", "")
    if owner and reviewer and reviewer in str(owner):
        return True
    # writers and managers may decide; readers may not.
    for key in ("writers", "managers"):
        entries = acl.get(key) or []
        if reviewer in [str(e) for e in entries]:
            return True
    return False
