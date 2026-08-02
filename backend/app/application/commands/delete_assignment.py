"""Command (CQRS intent) for deleting an Assignment."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class DeleteAssignmentCommand:
    """Intent to delete an Assignment (cascades to its submissions + blobs)."""

    object_id: ObjectId
