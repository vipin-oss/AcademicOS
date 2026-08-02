"""Query (CQRS intent) for listing Students.

Filters the manager UI and the AI lenses use: free-text ``q`` (name, roll,
registration, enrollment, email, programme, batch, tags), ``student_type``,
``programme``, ``semester``, ``section``, ``status``, and ``object_id``
(students linked to that Object — e.g. scholars of a supervisor, project
team members).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class ListStudentsQuery:
    """Intent to list Students with pagination and optional filters."""

    page: int = 1
    page_size: int = 20
    q: str | None = None
    student_type: str | None = None
    programme: str | None = None
    semester: int | None = None
    section: str | None = None
    status: str | None = None
    object_id: ObjectId | None = None
