"""JWT utilities.

Infrastructure layer: concrete token encode/decode. The auth *policy* (claims,
lifecycle) lives in the application layer; this module only signs/verifies.
"""
from __future__ import annotations

import datetime

import jwt

from app.core.config import settings


def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    payload: dict = {
        "sub": subject,
        "type": "access",
        "iat": now,
        "exp": now + datetime.timedelta(seconds=settings.access_token_ttl_seconds),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    payload = {
        "sub": subject,
        "type": "refresh",
        "iat": now,
        "exp": now + datetime.timedelta(seconds=settings.refresh_token_ttl_seconds),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
