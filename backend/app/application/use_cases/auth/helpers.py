"""Shared helpers for the Auth use cases (Sprint-1 authentication foundation).

Username is the USER object's title. Lookup is find-by-type plus a title
match: O(users) in memory, which is correct at auth scale and — unlike
JSONB containment — works identically on SQLite and PostgreSQL. If user
counts ever grow, a dedicated lookup (indexed column or metadata index)
is a later milestone; the helper isolates that decision to one place.
"""
from __future__ import annotations

from app.application.dtos.auth import KEY_PASSWORD_HASH, UserOutput
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType
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


def user_output(obj: UniversalObject) -> UserOutput:
    return UserOutput(
        id=str(obj.id),
        username=obj.title,
        created_at=obj.audit.created_at.isoformat() if obj.audit else "",
    )
