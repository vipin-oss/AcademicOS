"""Query (CQRS intent) for reading a single Research Project."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class GetProjectQuery:
    """Intent to fetch one Project by Object id."""

    object_id: ObjectId
