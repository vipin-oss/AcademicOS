"""Use case: authenticate a user and issue tokens (Sprint-1 auth foundation)."""
from __future__ import annotations

from app.application.commands.login_user import LoginUserCommand
from app.application.dtos.auth import KEY_PASSWORD_HASH, AuthTokensOutput
from app.application.exceptions import AuthenticationError
from app.application.ports.password_hasher import PasswordHasher
from app.application.ports.token_service import TokenService
from app.application.use_cases.auth.helpers import find_user
from app.application.validators.auth import assert_valid_login_input
from app.domain.repositories.object_repository import ObjectRepository


class LoginUserUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        token_service: TokenService,
        password_hasher: PasswordHasher,
    ) -> None:
        self._repository = repository
        self._token_service = token_service
        self._password_hasher = password_hasher

    def execute(self, command: LoginUserCommand) -> AuthTokensOutput:
        assert_valid_login_input(command.input)
        username = command.input.username.strip()

        user = find_user(self._repository, username)
        stored_hash = (
            user.metadata.get_value(KEY_PASSWORD_HASH) if user is not None else None
        )
        # One message for both failure modes: never reveal whether the
        # username exists (account enumeration protection).
        if user is None or stored_hash is None or not self._password_hasher.verify_password(
            command.input.password, stored_hash
        ):
            raise AuthenticationError("Invalid username or password.")

        return AuthTokensOutput(
            access_token=self._token_service.create_access_token(str(user.id)),
            refresh_token=self._token_service.create_refresh_token(str(user.id)),
        )
