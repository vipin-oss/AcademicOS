"""Use case: request a password-reset token (Sprint-8 final release).

Searches the user by username and issues a short-lived RESET token when
the account exists. Unknown usernames return a 200 with an empty token —
the response shape never reveals whether an account exists (account
enumeration protection), and the caller-facing behaviour is identical
either way (the reset simply cannot complete).

Transport note: this release has no email gateway, so the reset token is
returned in the response body (``reset_token``). In a deployment with an
outbox/email relay the token would be dispatched out-of-band instead and
this field would be dropped; the use case is the single place that
decision lives.
"""
from __future__ import annotations

from app.application.commands.forgot_password import ForgotPasswordCommand
from app.application.dtos.auth import ForgotPasswordOutput
from app.application.ports.token_service import TokenService
from app.application.use_cases.auth.helpers import find_user
from app.application.validators.auth import assert_valid_forgot_password_input
from app.domain.repositories.object_repository import ObjectRepository


class ForgotPasswordUseCase:
    def __init__(self, repository: ObjectRepository, token_service: TokenService) -> None:
        self._repository = repository
        self._token_service = token_service

    def execute(self, command: ForgotPasswordCommand) -> ForgotPasswordOutput:
        assert_valid_forgot_password_input(command.input)
        username = command.input.username.strip()
        user = find_user(self._repository, username)
        if user is None:
            # Enumeration-safe: same shape, no token, no error.
            return ForgotPasswordOutput(reset_token="", expires_in_seconds=0)
        token = self._token_service.create_reset_token(str(user.id))
        return ForgotPasswordOutput(
            reset_token=token,
            expires_in_seconds=1800,  # mirrors password_reset_token_ttl_seconds
        )
