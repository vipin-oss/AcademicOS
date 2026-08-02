"""Command (CQRS intent) for enrolling students into a Class."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class EnrollStudentsCommand:
    """Intent to register one or more students in a Class roster
    (ENROLLED_IN edges, written on each Student Object)."""

    class_id: ObjectId
    student_ids: tuple[ObjectId, ...]
    actor: str = "system"
