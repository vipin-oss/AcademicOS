"""Command (CQRS intent) for updating an Assignment."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.teaching import UpdateAssignmentInput
from app.domain.value_objects.object_id import ObjectId


@dataclass
class UpdateAssignmentCommand:
    """Intent to update an existing Assignment (partial; merge semantics)."""

    object_id: ObjectId
    input: UpdateAssignmentInput
