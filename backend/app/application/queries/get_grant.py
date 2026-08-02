"""Query (CQRS intent) for reading a single Grant."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class GetGrantQuery:
    """Intent to fetch one Grant by Object id."""

    object_id: ObjectId
