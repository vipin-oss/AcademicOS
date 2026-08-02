"""Command (CQRS intent) for grading a Submission."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class GradeSubmissionCommand:
    """Intent to grade a Submission (marks / feedback / rubric breakdown)."""

    object_id: ObjectId
    marks: float | None = None
    faculty_feedback: str | None = None
    rubric_score: tuple[dict, ...] | None = None
    actor: str = "system"
