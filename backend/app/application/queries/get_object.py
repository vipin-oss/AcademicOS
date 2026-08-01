"""Query (CQRS intent) for fetching a Universal Object."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class GetObjectQuery:
    """Intent to retrieve a Universal Object by its id."""

    object_id: ObjectId
