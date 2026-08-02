"""Command (CQRS intent) for bulk-enrolling students from a CSV."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class EnrollFromCsvCommand:
    """Intent to enroll students into a Class from CSV text (PART C/F).

    Each row resolves an EXISTING student by roll number (or e-mail); new
    students are admitted first through the student CSV import — admission
    and enrollment stay separate, single-responsibility write paths.
    """

    class_id: ObjectId
    text: str
    actor: str = "system"
