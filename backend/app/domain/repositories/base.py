"""Generic repository port (interface only — no implementation).

Frozen reference: Clean Architecture + Repository Pattern. The domain declares
the *contract*; the infrastructure layer (PostgreSQL, Qdrant) provides the
concrete adapters later. This module contains **no** implementation and no
framework imports — it is pure abstraction.

A repository is the only way the application layer persists or loads an
aggregate. ``save`` is intentionally the single write path; the aggregate's
emitted domain events are projected separately by the application layer.
"""
from __future__ import annotations

import abc
from typing import Generic, TypeVar

from app.domain.entities.base import Entity
from app.domain.value_objects.object_id import ObjectId

T = TypeVar("T", bound=Entity)


class Repository(abc.ABC, Generic[T]):
    @abc.abstractmethod
    def save(self, entity: T) -> None:
        """Persist or update the aggregate (single write path)."""

    @abc.abstractmethod
    def get_by_id(self, id: ObjectId) -> T | None:
        """Return the aggregate or ``None`` if it does not exist."""

    @abc.abstractmethod
    def find_by_ids(self, ids: list[ObjectId]) -> list[T]:
        """Return aggregates for the given ids (missing ids are skipped)."""

    @abc.abstractmethod
    def exists(self, id: ObjectId) -> bool:
        """True if an aggregate with this id is stored."""

    @abc.abstractmethod
    def delete(self, id: ObjectId) -> None:
        """Soft-delete semantics are defined by the infrastructure adapter."""
