"""Query (CQRS intent) for paginated listing of Documents.

Mirrors ``ListObjectsQuery`` and adds the one filter the frontend uses:
``object_id`` restricts the listing to documents linked to that Object
(``GET /documents?object_id=…``).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class ListDocumentsQuery:
    """Intent to list Documents with pagination and an optional link filter."""

    page: int = 1
    page_size: int = 20
    object_id: ObjectId | None = None
