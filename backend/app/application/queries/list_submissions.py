"""Query (CQRS intent) for listing Submissions."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class ListSubmissionsQuery:
    """Intent to list Submission Objects.

    At least one of ``assignment_id`` / ``student_id`` must be given —
    submissions are always read through a lens (an assignment's inbox, or
    a student's own submission history for the student dashboard).
    ``state`` filters to ``submitted`` | ``late`` | ``graded``.
    """

    assignment_id: ObjectId | None = None
    student_id: ObjectId | None = None
    state: str | None = None
    page: int = 1
    page_size: int = 50
