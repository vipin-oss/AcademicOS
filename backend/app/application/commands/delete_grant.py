"""Command (CQRS intent) for deleting a Grant."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class DeleteGrantCommand:
    """Intent to delete a Grant Object (its installment/expenditure children go with it)."""

    object_id: ObjectId
