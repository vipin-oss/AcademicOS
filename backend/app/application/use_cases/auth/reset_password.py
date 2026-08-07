"""Use case: set a new password via a valid reset token (final release)."""
from __future__ import annotations

from app.application.commands.reset_password import ResetPasswordCommand
from app.application.exceptions import AuthenticationError
from app.application.ports.password_hasher import PasswordHasher
from app.application.ports.token_service import TokenService
from app.application.use_cases.auth.helpers import set_password_hash
from app.application.validators.auth import assert_valid_reset_password_input
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType
from app.domain.value_objects.object_id import ObjectId


class ResetPasswordUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        token_service: TokenService,
        password_hasher: PasswordHasher,
    ) -> None:
        self._repository = repository
        self._token_service = token_service
        self._password_hasher = password_hasher

    def execute(self, command: ResetPasswordCommand) -> None:
        assert_valid_reset_password_input(command.input)
        try:
            claims = self._token_service.decode_token(command.input.reset_token.strip())
        except Exception as exc:  # noqa: BLE001 — normalise any decode failure
            raise AuthenticationError("Invalid or expired reset token.") from exc
        if claims.get("type") != "reset":
            raise AuthenticationError("Invalid or expired reset token.")
        subject = claims.get("sub")
        if subject is None:
            raise AuthenticationError("Invalid or expired reset token.")
        user = self._repository.get_by_id(ObjectId(subject))
        if user is None or user.object_type is not ObjectType.USER:
            # The account no longer exists — the reset token is dead.
            raise AuthenticationError("Invalid or expired reset token.")
        set_password_hash(
            user, self._password_hasher.hash_password(command.input.new_password)
        )
        self._repository.save(user)
