"""Use cases: read and update an object's ACL (Sprint-2 M1)."""
from __future__ import annotations

import json

from app.application.dtos.object import ACL_MANAGERS, ACL_READERS, ACL_WRITERS
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import UserRole
from app.domain.value_objects.metadata import MetadataEntry, MetadataLayer, Provenance
from app.domain.value_objects.object_id import ObjectId

_VALID_ROLES = {role.value for role in UserRole}


def _validate_entries(entries: list[str], field: str) -> None:
    for entry in entries:
        cleaned = entry.strip()
        if not cleaned:
            raise ValidationError(f"{field} entries must not be empty.")
        if cleaned.startswith("obj:"):
            continue
        if cleaned.startswith("role:") and cleaned[len("role:"):] in _VALID_ROLES:
            continue
        raise ValidationError(
            f"{field} entry {entry!r} must be an object id or role:<name>."
        )


def get_object_acl(repository: ObjectRepository, object_id: str) -> dict:
    obj = repository.get_by_id(ObjectId(object_id))
    if obj is None:
        raise ObjectNotFoundError(f"Object not found: {object_id}")
    return _acl_of(obj)


def update_object_acl(repository: ObjectRepository, object_id: str, acl: dict) -> dict:
    obj = repository.get_by_id(ObjectId(object_id))
    if obj is None:
        raise ObjectNotFoundError(f"Object not found: {object_id}")

    readers = [str(e).strip() for e in (acl.get("readers") or [])]
    writers = [str(e).strip() for e in (acl.get("writers") or [])]
    managers = [str(e).strip() for e in (acl.get("managers") or [])]
    _validate_entries(readers, "readers")
    _validate_entries(writers, "writers")
    _validate_entries(managers, "managers")

    _set_acl_entry(obj, ACL_READERS, readers)
    _set_acl_entry(obj, ACL_WRITERS, writers)
    _set_acl_entry(obj, ACL_MANAGERS, managers)
    repository.save(obj)
    return _acl_of(obj)


def _set_acl_entry(obj: UniversalObject, key: str, entries: list[str]) -> None:
    obj.set_metadata(
        MetadataEntry(
            key,
            json.dumps(entries, ensure_ascii=False),
            MetadataLayer.L1_SYSTEM,
            Provenance.SYSTEM,
        ),
        actor="system",
    )


def object_acl_scope(obj: UniversalObject) -> str | None:
    """Serialize an object's ACL metadata into the R4 evaluator's scope.

    Single source of truth for both the graph runtime and the route-level
    enforcement dependency (S2 M2 — removed the duplicated helper).
    """
    return json.dumps(_acl_of(obj))


def _acl_of(obj: UniversalObject) -> dict:
    def _list(key: str) -> list[str]:
        raw = obj.metadata.get_value(key)
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return []
        return [str(e) for e in parsed if isinstance(e, str)]

    return {
        "owner": obj.audit.created_by if obj.audit else "",
        "readers": _list(ACL_READERS),
        "writers": _list(ACL_WRITERS),
        "managers": _list(ACL_MANAGERS),
    }
