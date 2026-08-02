"""Query (CQRS intent) for listing Assignments.

Filters: ``class_id`` (the owning Class), free-text ``q`` (title /
description / instructions), ``assignment_type``, ``visibility``,
``status`` and ``object_id`` — the class lens
(``GET /teaching/assignments?object_id=<class>``).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class ListAssignmentsQuery:
    """Intent to list Assignments with pagination and optional filters."""

    page: int = 1
    page_size: int = 20
    class_id: ObjectId | None = None
    q: str | None = None
    assignment_type: str | None = None
    visibility: str | None = None
    status: str | None = None
    object_id: ObjectId | None = None  # lens: assignments of this Class
