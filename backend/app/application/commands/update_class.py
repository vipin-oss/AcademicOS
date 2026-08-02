"""Command (CQRS intent) for updating a Class."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.teaching import UpdateClassInput
from app.domain.value_objects.object_id import ObjectId


@dataclass
class UpdateClassCommand:
    """Intent to update an existing Class (partial; merge semantics)."""

    object_id: ObjectId
    input: UpdateClassInput
