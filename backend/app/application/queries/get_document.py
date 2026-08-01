"""Query (CQRS intent) for fetching a single Document.

Mirrors ``GetObjectQuery``.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class GetDocumentQuery:
    """Intent to retrieve a Document by its id."""

    object_id: ObjectId
