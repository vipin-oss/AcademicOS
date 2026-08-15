"""Auth DTOs (Sprint-1 authentication foundation).

Scope guard: this milestone authenticates identities only — no roles, no
permissions, no authorisation decisions (later Sprint-1 milestones).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Credential + role storage on the USER object (system-layer metadata).
KEY_PASSWORD_HASH = "auth.password_hash"
KEY_ROLES = "auth.roles"  # JSON-encoded list of UserRole values


@dataclass
class RegisterUserInput:
    username: str  # -> Object title (unique per account)
    password: str


@dataclass
class LoginInput:
    username: str
    password: str


@dataclass
class RefreshInput:
    refresh_token: str


@dataclass
class AuthTokensOutput:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@dataclass
class UserOutput:
    id: str
    username: str
    created_at: str
    roles: list[str] = field(default_factory=list)


@dataclass
class AssignRolesInput:
    user_id: str
    roles: list[str]


@dataclass
class ForgotPasswordInput:
    username: str


@dataclass
class ResetPasswordInput:
    reset_token: str
    new_password: str


@dataclass
class ForgotPasswordOutput:
    reset_token: str
    expires_in_seconds: int
