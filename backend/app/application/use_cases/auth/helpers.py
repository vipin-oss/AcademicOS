"""Shared helpers for the Auth use cases (Sprint-1 auth foundation + M3 roles).

Username is the USER object's title. Lookup is find-by-type plus a title
match: O(users) in memory, which is correct at auth scale and — unlike
JSONB containment — works identically on SQLite and PostgreSQL. If user
counts ever grow, a dedicated lookup (indexed column or metadata index)
is a later milestone; the helper isolates that decision to one place.

Roles are stored on the USER object as ``auth.roles`` system metadata
(JSON-encoded list of ``UserRole`` values). System layer = never projected
through the generic objects API (the M1 security fix), so roles are
internal to the auth machinery.
"""
from __future__ import annotations

import json

from app.application.dtos.auth import KEY_PASSWORD_HASH, KEY_ROLES, UserOutput
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, UserRole
from app.domain.value_objects.metadata import MetadataEntry, MetadataLayer, Provenance


def find_user(repository: ObjectRepository, username: str) -> UniversalObject | None:
    """The USER object whose title equals ``username``, or None."""
    for obj in repository.find_by_type(ObjectType.USER):
        if obj.title == username:
            return obj
    return None


def set_password_hash(obj: UniversalObject, password_hash: str) -> None:
    """Store the credential as a system-layer metadata entry."""
    obj.set_metadata(
        MetadataEntry(
            KEY_PASSWORD_HASH,
            password_hash,
            MetadataLayer.L1_SYSTEM,
            Provenance.SYSTEM,
        ),
        actor="system",
    )


def get_roles(obj: UniversalObject) -> list[str]:
    """The user's role values (empty list when none assigned)."""
    raw = obj.metadata.get_value(KEY_ROLES)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return [r for r in parsed if isinstance(r, str)]


def set_roles(obj: UniversalObject, roles: list[str]) -> None:
    """Replace the user's roles (system-layer metadata write)."""
    obj.set_metadata(
        MetadataEntry(
            KEY_ROLES,
            json.dumps(roles, ensure_ascii=False),
            MetadataLayer.L1_SYSTEM,
            Provenance.SYSTEM,
        ),
        actor="system",
    )


def bootstrap_admin(repository: ObjectRepository, username: str | None) -> bool:
    """Promote ``username`` to ADMIN at startup when it has no roles.

    Idempotent: a user that already holds roles is never touched (so an
    operator can demote the bootstrap admin later without it being
    re-promoted). Returns True when a promotion happened.
    """
    if not username:
        return False
    user = find_user(repository, username.strip())
    if user is None or get_roles(user):
        return False
    set_roles(user, [UserRole.ADMIN.value])
    repository.save(user)
    return True


def user_output(obj: UniversalObject) -> UserOutput:
    return UserOutput(
        id=str(obj.id),
        username=obj.title,
        created_at=obj.audit.created_at.isoformat() if obj.audit else "",
        roles=get_roles(obj),
    )
