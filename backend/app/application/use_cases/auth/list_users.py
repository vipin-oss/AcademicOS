"""Use case: list user accounts (Sprint-1 M3 — RBAC).

Admin-only at the API layer. Exposes id, username, created_at and the
assigned roles.
"""
from __future__ import annotations

from app.application.dtos.auth import UserOutput
from app.application.use_cases.auth.helpers import user_output
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class ListUsersUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self) -> list[UserOutput]:
        users = self._repository.find_by_type(ObjectType.USER)
        users.sort(key=lambda u: u.title.lower())
        return [user_output(u) for u in users]
