"""Query (CQRS intent) for listing Research Projects.

Filters (PART 9): free-text ``q`` (title/code/objectives/abstract/keywords),
``pi`` (team member names), ``agency`` (linked agency names), ``status``
(lifecycle), ``year`` (start year), ``department``; plus ``object_id`` lens
(projects linked to that Object).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class ListProjectsQuery:
    """Intent to list Projects with pagination and optional filters."""

    page: int = 1
    page_size: int = 20
    q: str | None = None
    pi: str | None = None
    agency: str | None = None
    status: str | None = None  # lifecycle_status
    year: int | None = None
    department: str | None = None
    object_id: ObjectId | None = None
