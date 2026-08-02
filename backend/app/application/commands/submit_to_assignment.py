"""Command (CQRS intent) for a student's Submission to an Assignment."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class SubmitToAssignmentCommand:
    """Intent to record a Submission for (assignment, student).

    One submission per pair: resubmitting uploads a new file onto the SAME
    Submission Object (version history via the aggregate's version)."""

    assignment_id: ObjectId
    student_id: ObjectId
    file_name: str | None = None
    content: bytes | None = None
    mime_type: str | None = None
    comments: str | None = None
    submitted_at: str | None = None  # None -> now (SYSTEM); faculty can back-date
    actor: str = "system"
