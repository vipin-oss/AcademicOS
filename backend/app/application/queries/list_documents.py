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
    """Intent to list Documents with pagination and an optional link filter.

    ``owner_user_id`` is the requesting principal's id (2026-09 audit
    follow-up): every list is scoped to the caller's own Documents, never a
    global directory. It is not client-suppliable — the route handler sets
    it from the authenticated ``get_current_user`` dependency, the same way
    ``created_by`` is already stamped server-side on create.
    """

    page: int = 1
    page_size: int = 20
    object_id: ObjectId | None = None
    owner_user_id: str | None = None
