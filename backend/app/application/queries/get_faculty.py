"""Query (CQRS intent) for reading a single Faculty member."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class GetFacultyQuery:
    """Intent to fetch one Faculty member by Object id."""

    object_id: ObjectId
