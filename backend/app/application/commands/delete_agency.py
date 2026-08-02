"""Command (CQRS intent) for deleting a Funding Agency."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class DeleteAgencyCommand:
    """Intent to delete a Funding Agency Object."""

    object_id: ObjectId
