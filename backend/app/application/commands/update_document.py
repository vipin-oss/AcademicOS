"""Command (CQRS intent) for updating a Document.

Mirrors ``UpdateObjectCommand``: intent + the Object id it targets.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.document import UpdateDocumentInput
from app.domain.value_objects.object_id import ObjectId


@dataclass
class UpdateDocumentCommand:
    """Intent to update the Document identified by ``object_id``."""

    object_id: ObjectId
    input: UpdateDocumentInput
