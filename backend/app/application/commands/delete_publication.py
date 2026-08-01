"""Command (CQRS intent) for deleting a Publication.

Mirrors ``DeleteObjectCommand``: intent carries only the Object id.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class DeletePublicationCommand:
    """Intent to delete the Publication identified by ``object_id``."""

    object_id: ObjectId
