"""Authentication dependencies for the API layer (Sprint-1 foundation).

- ``get_current_principal``: extracts and verifies the bearer JWT, returns
  the decoded claims (kept for the JWT-decode-only contract).
- ``get_current_user``: the authenticated USER object — verifies the token,
  requires an access token (refresh tokens are never accepted here), loads
  the account, and 401s when the account no longer exists. Future
  Sprint-1 milestones protect routes with this dependency.
"""
from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.dependencies.db import get_db
from app.core.exceptions import UnauthorizedError
from app.domain.value_objects.enums import ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.auth.jwt import decode_token
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)

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


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """The authenticated USER object, or 401."""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Missing bearer token")
    try:
        claims = decode_token(credentials.credentials)
    except Exception as exc:  # noqa: BLE001 - normalise to domain error
        raise UnauthorizedError("Invalid or expired token") from exc

    if claims.get("type") != "access":
        # A refresh token must never satisfy a protected endpoint.
        raise UnauthorizedError("Invalid or expired token")

    repo = SQLAlchemyObjectRepository(db)
    user = repo.get_by_id(ObjectId(claims["sub"]))
    if user is None or user.object_type is not ObjectType.USER:
        # The account no longer exists — the token is dead.
        raise UnauthorizedError("Invalid or expired token")
    return user
