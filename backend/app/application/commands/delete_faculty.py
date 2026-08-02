"""Command (CQRS intent) for deleting a Faculty member."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class DeleteFacultyCommand:
    """Intent to delete a Faculty Object."""

    object_id: ObjectId
