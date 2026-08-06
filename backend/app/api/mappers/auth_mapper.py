"""Pure mapping between auth API shapes and Application DTOs.

Framework-free (no FastAPI/Pydantic/SQLAlchemy imports) so it is
unit-testable without those dependencies.
"""
from __future__ import annotations

from app.application.dtos.auth import (
    AuthTokensOutput,
    LoginInput,
    RefreshInput,
    RegisterUserInput,
    UserOutput,
)


def to_register_input(*, username: str, password: str) -> RegisterUserInput:
    return RegisterUserInput(username=username, password=password)


def to_login_input(*, username: str, password: str) -> LoginInput:
    return LoginInput(username=username, password=password)


def to_refresh_input(*, refresh_token: str) -> RefreshInput:
    return RefreshInput(refresh_token=refresh_token)


def to_tokens_response(out: AuthTokensOutput) -> dict:
    return {
        "access_token": out.access_token,
        "refresh_token": out.refresh_token,
        "token_type": out.token_type,
    }


def to_user_response(out: UserOutput) -> dict:
    return {
        "id": out.id,
        "username": out.username,
        "created_at": out.created_at,
        "roles": out.roles,
    }
