"""Use case: exchange a valid refresh token for a fresh token pair."""
from __future__ import annotations

from app.application.commands.refresh_tokens import RefreshTokensCommand
from app.application.dtos.auth import AuthTokensOutput
from app.application.exceptions import AuthenticationError
from app.application.ports.token_service import TokenService
from app.application.validators.auth import assert_valid_refresh_input
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType
from app.domain.value_objects.object_id import ObjectId


class RefreshTokensUseCase:
    def __init__(self, repository: ObjectRepository, token_service: TokenService) -> None:
        self._repository = repository
        self._token_service = token_service

    def execute(self, command: RefreshTokensCommand) -> AuthTokensOutput:
        assert_valid_refresh_input(command.input)
        token = command.input.refresh_token.strip()

        try:
            claims = self._token_service.decode_token(token)
        except AuthenticationError:
            raise
        except Exception as exc:  # noqa: BLE001 — normalise any decode failure
            raise AuthenticationError("Invalid or expired refresh token.") from exc

        if claims.get("type") != "refresh":
            raise AuthenticationError("Invalid or expired refresh token.")

        user = self._repository.get_by_id(ObjectId(claims["sub"]))
        if user is None or user.object_type is not ObjectType.USER:
            # The account no longer exists — the refresh token is dead.
            raise AuthenticationError("Invalid or expired refresh token.")

        return AuthTokensOutput(
            access_token=self._token_service.create_access_token(str(user.id)),
            refresh_token=self._token_service.create_refresh_token(str(user.id)),
        )
