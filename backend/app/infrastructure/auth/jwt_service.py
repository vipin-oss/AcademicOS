"""JWT adapter for the TokenService port.

Wraps the existing JWT utilities (app.infrastructure.auth.jwt) so the
application layer stays infrastructure-free (guardrail). Decode failures
are normalised to ``AuthenticationError``.
"""
from __future__ import annotations

from app.application.exceptions import AuthenticationError
from app.application.ports.token_service import TokenService
from app.infrastructure.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
)


class JwtTokenService(TokenService):
    def create_access_token(self, subject: str) -> str:
        return create_access_token(subject)

    def create_refresh_token(self, subject: str) -> str:
        return create_refresh_token(subject)

    def decode_token(self, token: str) -> dict:
        try:
            return decode_token(token)
        except Exception as exc:  # noqa: BLE001 — normalise any decode failure
            raise AuthenticationError("Invalid or expired token.") from exc
