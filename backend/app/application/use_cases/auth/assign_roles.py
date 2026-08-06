"""Use case: assign roles to a user (Sprint-1 M3 — RBAC).

Admin-only at the API layer. Roles are validated against the vocabulary
before persisting, so an unknown role can never be stored.
"""
from __future__ import annotations

from app.application.commands.assign_roles import AssignRolesCommand
from app.application.dtos.auth import UserOutput
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.use_cases.auth.helpers import set_roles, user_output
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, UserRole
from app.domain.value_objects.object_id import ObjectId

_VALID_ROLES = {role.value for role in UserRole}


class AssignRolesUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: AssignRolesCommand) -> UserOutput:
        user_id = command.input.user_id.strip()
        roles = [role.strip() for role in command.input.roles]
        unknown = sorted(set(roles) - _VALID_ROLES)
        if unknown:
            raise ValidationError(f"Unknown role(s): {', '.join(unknown)}")

        obj = self._repository.get_by_id(ObjectId(user_id))
        if obj is None or obj.object_type is not ObjectType.USER:
            raise ObjectNotFoundError(f"User not found: {user_id}")

        # Deduplicate, preserve order.
        seen: set[str] = set()
        cleaned = [r for r in roles if not (r in seen or seen.add(r))]
        set_roles(obj, cleaned)
        self._repository.save(obj)
        return user_output(obj)
