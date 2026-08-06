"""Application port: password hashing (Sprint-1 authentication foundation).

Keeps the auth use cases free of infrastructure imports (guardrail); the
bcrypt adapter lives in ``infrastructure/auth``.
"""
from __future__ import annotations

import abc


class PasswordHasher(abc.ABC):
    @abc.abstractmethod
    def hash_password(self, password: str) -> str:
        """Hash a plaintext password."""

    @abc.abstractmethod
    def verify_password(self, password: str, password_hash: str) -> bool:
        """True when the plaintext matches the stored hash (never raises)."""
