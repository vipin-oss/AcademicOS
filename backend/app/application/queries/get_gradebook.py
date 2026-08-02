"""Query (CQRS intent) for the computed Gradebook of a Class (PART H)."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class GetGradebookQuery:
    """Intent to compute the weighted marks matrix of one Class."""

    class_id: ObjectId
