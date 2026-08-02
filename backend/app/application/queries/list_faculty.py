"""Query (CQRS intent) for listing the Faculty directory."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ListFacultyQuery:
    """Intent to list Faculty with pagination, search and directory filters."""

    page: int = 1
    page_size: int = 20
    q: str | None = None
    department: str | None = None
    designation: str | None = None
    employment_type: str | None = None
    status: str | None = None
