"""Query (CQRS intent) for reading a single Student."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class GetStudentQuery:
    """Intent to fetch one Student by Object id."""

    object_id: ObjectId
