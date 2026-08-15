"""Application port: saved-view store (V3 M13, ADR-060)."""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass(frozen=True)
class SavedViewRecord:
    id: str
    name: str
    definition: dict
    owner_user_id: str = "default"
    created_at: str = ""


class SavedViewStore(abc.ABC):
    @abc.abstractmethod
    def add(self, view: SavedViewRecord) -> SavedViewRecord:
        """Save a view definition (idempotent by id)."""

    @abc.abstractmethod
    def get(self, view_id: str) -> SavedViewRecord | None:
        """Fetch a view by id, or None."""

    @abc.abstractmethod
    def list_for_owner(self, owner_user_id: str) -> list[SavedViewRecord]:
        """All views owned by a user, newest first."""

    @abc.abstractmethod
    def delete(self, view_id: str) -> None:
        """Remove a view (missing id is ignored)."""
