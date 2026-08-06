"""Auth DTOs (Sprint-1 authentication foundation).

Scope guard: this milestone authenticates identities only — no roles, no
permissions, no authorisation decisions (later Sprint-1 milestones).
"""
from __future__ import annotations

from dataclasses import dataclass

# Credential storage on the USER object (system-layer metadata).
KEY_PASSWORD_HASH = "auth.password_hash"


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
