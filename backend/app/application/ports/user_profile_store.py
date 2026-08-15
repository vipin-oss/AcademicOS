"""Application port: user-profile projection store (V3 M16 wave 1, ADR-063)."""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    username: str
    display_name: str
    roles: str = "[]"
    institution: str | None = None


class UserProfileStore(abc.ABC):
    @abc.abstractmethod
    def upsert(self, profile: UserProfile) -> UserProfile:
        """Write one profile (idempotent; derived from the USER object)."""

    @abc.abstractmethod
    def get(self, user_id: str) -> UserProfile | None:
        """Fetch a profile, or None (caller falls back to the object store)."""

    @abc.abstractmethod
    def list(self) -> list[UserProfile]:
        """All profiles (projection read; the object store remains authority)."""

    @abc.abstractmethod
    def clear(self) -> None:
        """Drop every profile row (rebuild / rollback path)."""
