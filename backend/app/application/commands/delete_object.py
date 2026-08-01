"""Command (CQRS intent) for deleting a Universal Object."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class DeleteObjectCommand:
    """Intent to delete a Universal Object identified by ``object_id``."""

    object_id: ObjectId
