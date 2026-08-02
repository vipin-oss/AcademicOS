"""Query (CQRS intent) for reading the roster of a Class."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class GetRosterQuery:
    """Intent to list the enrolled students of one Class (PART C)."""

    class_id: ObjectId
