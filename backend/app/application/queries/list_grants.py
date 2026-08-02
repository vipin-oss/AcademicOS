"""Query (CQRS intent) for listing Grants.

Filters: free-text ``q`` (grant number/title/schedule), ``project_id``
(grants funding that project), ``agency_id`` (grants of that agency),
``status`` (universal lifecycle).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class ListGrantsQuery:
    """Intent to list Grants with pagination and optional filters."""

    page: int = 1
    page_size: int = 20
    q: str | None = None
    project_id: ObjectId | None = None
    agency_id: ObjectId | None = None
    status: str | None = None
