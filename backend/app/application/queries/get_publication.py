"""Query (CQRS intent) for fetching a single Publication.

Mirrors ``GetObjectQuery``.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class GetPublicationQuery:
    """Intent to retrieve a Publication by its id."""

    object_id: ObjectId
