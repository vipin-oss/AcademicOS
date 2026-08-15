"""JWT utilities.

Infrastructure layer: concrete token encode/decode. The auth *policy* (claims,
lifecycle) lives in the application layer; this module only signs/verifies.
"""
from __future__ import annotations

import datetime
import uuid

import jwt

from app.core.config import settings


def _new_jti() -> str:
    return uuid.uuid4().hex


def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    payload: dict = {
        "sub": subject,
        "type": "access",
        "jti": _new_jti(),  # V3 M9: revocation id
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
        "jti": _new_jti(),  # V3 M9: revocation id
        "iat": now,
        "exp": now + datetime.timedelta(seconds=settings.refresh_token_ttl_seconds),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_reset_token(subject: str) -> str:
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    payload = {
        "sub": subject,
        "type": "reset",
        "iat": now,
        "exp": now + datetime.timedelta(seconds=settings.password_reset_token_ttl_seconds),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
