"""Command (CQRS intent) for updating a Faculty member."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.faculty import UpdateFacultyInput
from app.domain.value_objects.object_id import ObjectId


@dataclass
class UpdateFacultyCommand:
    """Intent to update a Faculty member (frozen merge contract)."""

    object_id: ObjectId
    input: UpdateFacultyInput
