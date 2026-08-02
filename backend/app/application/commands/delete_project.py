"""Command (CQRS intent) for deleting a Research Project."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class DeleteProjectCommand:
    """Intent to delete a Project Object (its milestone children go with it)."""

    object_id: ObjectId
