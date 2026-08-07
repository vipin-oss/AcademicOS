"""Auth input validation (Sprint-1 authentication foundation)."""
from __future__ import annotations

from app.application.dtos.auth import (
    ForgotPasswordInput,
    LoginInput,
    RefreshInput,
    RegisterUserInput,
    ResetPasswordInput,
)
from app.application.exceptions import ValidationError

_USERNAME_MAX = 64
_PASSWORD_MIN = 8
# bcrypt's hard input cap (see infrastructure/auth/passwords.py).
_PASSWORD_MAX_BYTES = 72


def _validate_username(username: str) -> list[str]:
    errors: list[str] = []
    cleaned = username.strip()
    if not cleaned:
        errors.append("username must not be empty.")
    elif len(cleaned) > _USERNAME_MAX:
        errors.append(f"username must be at most {_USERNAME_MAX} characters.")
    return errors


def _validate_password(password: str) -> list[str]:
    errors: list[str] = []
    if len(password) < _PASSWORD_MIN:
        errors.append(f"password must be at least {_PASSWORD_MIN} characters.")
    if len(password.encode("utf-8")) > _PASSWORD_MAX_BYTES:
        errors.append(f"password must be at most {_PASSWORD_MAX_BYTES} bytes.")
    return errors


def assert_valid_register_input(dto: RegisterUserInput) -> None:
    errors = _validate_username(dto.username) + _validate_password(dto.password)
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_login_input(dto: LoginInput) -> None:
    errors = _validate_username(dto.username)
    if not dto.password:
        errors.append("password must not be empty.")
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_refresh_input(dto: RefreshInput) -> None:
    if not dto.refresh_token.strip():
        raise ValidationError("refresh_token must not be empty.")


def assert_valid_forgot_password_input(dto: ForgotPasswordInput) -> None:
    errors = _validate_username(dto.username)
    if errors:
        raise ValidationError("; ".join(errors))


def assert_valid_reset_password_input(dto: ResetPasswordInput) -> None:
    errors: list[str] = []
    if not dto.reset_token.strip():
        errors.append("reset_token must not be empty.")
    errors += _validate_password(dto.new_password)
    if errors:
        raise ValidationError("; ".join(errors))
