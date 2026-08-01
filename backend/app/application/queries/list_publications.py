"""Query (CQRS intent) for listing Publications.

Adds the reference-manager filters the frontend and future AI lenses use:
free-text ``q`` (title/authors/DOI/journal/keywords/publisher/ISBN/ISSN),
``publication_type``, ``year``, ``quartile``, ``pipeline_stage``, ``status``,
and ``object_id`` (publications linked to that Object, any relationship kind).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class ListPublicationsQuery:
    """Intent to list Publications with pagination and optional filters."""

    page: int = 1
    page_size: int = 20
    q: str | None = None
    publication_type: str | None = None
    year: int | None = None
    quartile: str | None = None
    pipeline_stage: str | None = None
    status: str | None = None
    object_id: ObjectId | None = None
