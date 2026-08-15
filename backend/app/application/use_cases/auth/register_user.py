"""Use case: register a user account (Sprint-1 authentication foundation)."""
from __future__ import annotations

import hashlib

from app.application.commands.register_user import RegisterUserCommand
from app.application.dtos.auth import UserOutput
from app.application.exceptions import ObjectAlreadyExistsError
from app.application.ports.password_hasher import PasswordHasher
from app.application.use_cases.auth.helpers import (
    find_user,
    set_password_hash,
    user_output,
)
from app.application.validators.auth import assert_valid_register_input
from app.domain.entities.object import UniversalObject
from app.domain.exceptions import OptimisticConcurrencyError
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId


def _user_id_for(username: str) -> ObjectId:
    """Deterministic id derived from the username.

    Two concurrent registrations of the same username produce the SAME id,
    so the database's primary key — not a check-then-insert — decides the
    winner. The loser's INSERT hits the R3 optimistic-concurrency conflict
    and surfaces as a 409. (64-bit hash prefix: collision probability is
    negligible below billions of accounts; ids stay immutable.)
    """
    digest = hashlib.sha256(username.encode("utf-8")).hexdigest()[:16].upper()
    return ObjectId(f"obj:user:{digest}")


class RegisterUserUseCase:
    def __init__(self, repository: ObjectRepository, password_hasher: PasswordHasher) -> None:
        self._repository = repository
        self._password_hasher = password_hasher

    def execute(self, command: RegisterUserCommand) -> UserOutput:
        assert_valid_register_input(command.input)
        username = command.input.username.strip()

        if find_user(self._repository, username) is not None:
            raise ObjectAlreadyExistsError(f"Username {username!r} is already taken.")

        obj = UniversalObject.create(
            object_type=ObjectType.USER,
            title=username,
            created_by="system",
            status=ObjectStatus.ACTIVE,
            object_id=_user_id_for(username),
        )
        set_password_hash(obj, self._password_hasher.hash_password(command.input.password))
        try:
            self._repository.save(obj)
        except OptimisticConcurrencyError:
            # A concurrent registration of the same username won the INSERT.
            raise ObjectAlreadyExistsError(
                f"Username {username!r} is already taken."
            ) from None
        return user_output(obj)
