"""Object repository port — domain-specific queries over UniversalObject.

Interface only. These are the *intentions* the domain needs; the concrete
adapter (PostgreSQL + Qdrant) decides how to satisfy them. No SQL, no vector
code, no implementation here.
"""
from __future__ import annotations

import abc

from app.domain.entities.object import UniversalObject
from app.domain.repositories.base import Repository
from app.domain.value_objects.enums import ObjectStatus, ObjectType, RelationshipKind
from app.domain.value_objects.object_id import ObjectId


class ObjectRepository(Repository[UniversalObject]):
    @abc.abstractmethod
    def find_by_type(self, object_type: ObjectType) -> list[UniversalObject]:
        """All Objects of a given type (e.g. every Course in the Space)."""

    @abc.abstractmethod
    def find_by_status(self, status: ObjectStatus) -> list[UniversalObject]:
        """All Objects in a given lifecycle state."""

    @abc.abstractmethod
    def find_related(
        self, object_id: ObjectId, kind: RelationshipKind | None = None
    ) -> list[ObjectId]:
        """Ids of Objects linked from ``object_id`` (optionally by relationship kind)."""

    @abc.abstractmethod
    def find_by_metadata(self, key: str, value: str | None = None) -> list[UniversalObject]:
        """Objects carrying a metadata key, optionally constrained to a value."""
