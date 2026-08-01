"""Command (CQRS intent) for deleting a Document.

Mirrors ``DeleteObjectCommand``: intent carries only the Object id.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class DeleteDocumentCommand:
    """Intent to delete the Document identified by ``object_id``."""

    object_id: ObjectId
