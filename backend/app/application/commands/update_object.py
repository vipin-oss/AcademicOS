"""Command (CQRS intent) for updating a Universal Object."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.object import UpdateObjectInput
from app.domain.value_objects.object_id import ObjectId


@dataclass
class UpdateObjectCommand:
    """Intent to update a Universal Object identified by ``object_id``."""

    object_id: ObjectId
    input: UpdateObjectInput
