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

    @abc.abstractmethod
    def find(
        self,
        *,
        object_type: ObjectType | None = None,
        status: ObjectStatus | None = None,
        metadata_key: str | None = None,
        metadata_value: str | None = None,
        page: int = 1,
        page_size: int = 0,
        sort_by: str | None = None,
        order: str = "asc",
    ) -> list[UniversalObject]:
        """Objects matching the optional filters (R2 — repository projections).

        ``page_size=0`` (default) returns every match, preserving the
        historical load-all behaviour exactly. With ``page_size > 0`` the
        result is the requested page.

        Ordering: when ``sort_by`` is given, the result is ordered by that
        column (``id``, ``object_type``, ``title``, ``status`` or
        ``version``) in ``order`` (``asc``/``desc``), with ``id`` as a
        deterministic tie-break — whether or not pagination is active.
        Paginating without ``sort_by`` defaults to ``id`` ascending so
        pages are stable across calls. Unsupported sort/order values raise
        ``ValueError``.
        """

    @abc.abstractmethod
    def count(
        self,
        *,
        object_type: ObjectType | None = None,
        status: ObjectStatus | None = None,
        metadata_key: str | None = None,
        metadata_value: str | None = None,
    ) -> int:
        """Total number of Objects matching the filters (unpaginated).

        Required by pagination consumers: the page size cannot expose the
        total, so ``count`` answers ``total_count`` for the same filters.
        """
