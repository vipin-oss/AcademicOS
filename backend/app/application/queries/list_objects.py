"""Query (CQRS intent) for paginated listing of Universal Objects."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.enums import ObjectStatus, ObjectType


@dataclass
class ListObjectsQuery:
    """Intent to list Objects with pagination and optional filters."""

    page: int = 1
    page_size: int = 20
    object_type: ObjectType | None = None
    status: ObjectStatus | None = None
