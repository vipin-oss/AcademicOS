"""Command (CQRS intent) for deleting a Class."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class DeleteClassCommand:
    """Intent to delete a Class. Its assignments/submissions/attendance
    sessions are cascade-deleted and reported (evidence is never silently
    orphaned)."""

    object_id: ObjectId
