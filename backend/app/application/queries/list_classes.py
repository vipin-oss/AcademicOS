"""Query (CQRS intent) for listing Classes.

Filters: free-text ``q`` (title, code, programme, batch), ``semester``,
``session``, ``status``, and ``object_id`` — the lens both dashboards need:
classes a STUDENT is enrolled in, and classes a FACULTY member teaches.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class ListClassesQuery:
    """Intent to list Classes with pagination and optional filters."""

    page: int = 1
    page_size: int = 20
    q: str | None = None
    semester: int | None = None
    session: str | None = None
    status: str | None = None
    object_id: ObjectId | None = None
