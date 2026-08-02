"""Command (CQRS intent) for removing a student from a Class roster."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class UnenrollStudentCommand:
    """Intent to remove one student from a Class roster."""

    class_id: ObjectId
    student_id: ObjectId
    actor: str = "system"
