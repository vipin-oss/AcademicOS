"""Input validation for object use cases.

Validation runs at the boundary, before the domain is touched. Raises
``ValidationError`` (application layer) so the presentation layer maps it to a
client error. Pure and framework-free.
"""
from __future__ import annotations

from app.application.dtos.object import CreateObjectInput, UpdateObjectInput
from app.application.exceptions import ValidationError
from app.application.queries.list_objects import ListObjectsQuery
from app.domain.value_objects.enums import ObjectStatus, ObjectType

# Security: the credential/role namespace (auth.*) is reserved for the auth
# machinery — the generic endpoints must never write these keys (a user could
# otherwise self-assign auth.roles = ["admin"]). The ACL namespace (acl.*) is
# likewise reserved: object permissions are written only through the
# dedicated ACL endpoint (Sprint-2 M1). The USER object type must never be
# created through the generic API (registration invariants).
_RESERVED_METADATA_PREFIXES = ("auth.", "acl.")


def validate_create_object_input(dto: CreateObjectInput) -> list[str]:
    errors: list[str] = []
    if not dto.title or not dto.title.strip():
        errors.append("Title must not be empty.")
    if not dto.created_by or not dto.created_by.strip():
        errors.append("created_by must identify an actor.")
    if dto.status not in (ObjectStatus.DRAFT, ObjectStatus.ACTIVE, ObjectStatus.ARCHIVED):
        errors.append("Initial status must be DRAFT, ACTIVE, or ARCHIVED.")
    if dto.metadata is not None:
        for entry in dto.metadata.entries:
            if not entry.key or not entry.key.strip():
                errors.append("Metadata key must not be empty.")
            if entry.key.startswith(_RESERVED_METADATA_PREFIXES):
                errors.append(f"Metadata key {entry.key!r} is reserved.")
    if dto.object_type is ObjectType.USER:
        errors.append("USER objects must be created through the auth endpoints.")
    return errors


def validate_update_object_input(dto: UpdateObjectInput) -> list[str]:
    errors: list[str] = []
    if not dto.updated_by or not dto.updated_by.strip():
        errors.append("updated_by must identify an actor.")
    if dto.status is not None and dto.status not in ObjectStatus:
        errors.append("Invalid status value.")
    if dto.metadata is not None:
        for entry in dto.metadata.entries:
            if not entry.key or not entry.key.strip():
                errors.append("Metadata key must not be empty.")
            if entry.key.startswith(_RESERVED_METADATA_PREFIXES):
                errors.append(f"Metadata key {entry.key!r} is reserved.")
    return errors


def validate_list_query(query: ListObjectsQuery) -> list[str]:
    errors: list[str] = []
    if query.page < 1:
        errors.append("page must be >= 1.")
    if query.page_size < 1:
        errors.append("page_size must be >= 1.")
    if query.page_size > 100:
        errors.append("page_size must be <= 100.")
    return errors


def assert_valid_create_object_input(dto: CreateObjectInput) -> None:
    errors = validate_create_object_input(dto)
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_update_object_input(dto: UpdateObjectInput) -> None:
    errors = validate_update_object_input(dto)
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_list_query(query: ListObjectsQuery) -> None:
    errors = validate_list_query(query)
    if errors:
        raise ValidationError("; ".join(errors))
