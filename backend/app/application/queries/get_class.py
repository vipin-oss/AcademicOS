"""Query (CQRS intent) for reading a single Class."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class GetClassQuery:
    """Intent to fetch one Class by Object id."""

    object_id: ObjectId
