"""Command (CQRS intent) for updating a Student."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.student import UpdateStudentInput
from app.domain.value_objects.object_id import ObjectId


@dataclass
class UpdateStudentCommand:
    """Intent to update an existing Student (partial; merge semantics)."""

    object_id: ObjectId
    input: UpdateStudentInput
