"""Command (CQRS intent) for deleting a Student."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class DeleteStudentCommand:
    """Intent to delete a Student Object."""

    object_id: ObjectId
