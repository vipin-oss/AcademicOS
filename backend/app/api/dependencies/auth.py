"""Authentication dependency adapter for the API layer.

Extracts and verifies the bearer JWT. Returns the decoded claims as the
"current principal". No user-lookup yet (domain layer comes later); this only
proves the auth wiring in the skeleton.
"""
from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import UnauthorizedError
from app.infrastructure.auth.jwt import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Missing bearer token")
    try:
        return decode_token(credentials.credentials)
    except Exception as exc:  # noqa: BLE001 - normalise to domain error
        raise UnauthorizedError("Invalid or expired token") from exc
