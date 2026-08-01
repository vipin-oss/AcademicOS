"""Command (CQRS intent) for updating a Publication.

Mirrors ``UpdateObjectCommand``: intent + the Object id it targets.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.publication import UpdatePublicationInput
from app.domain.value_objects.object_id import ObjectId


@dataclass
class UpdatePublicationCommand:
    """Intent to update the Publication identified by ``object_id``."""

    object_id: ObjectId
    input: UpdatePublicationInput
