"""Command (CQRS intent) for deleting a grant expenditure."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class DeleteExpenditureCommand:
    """Intent to delete an expenditure Object (correction path)."""

    expenditure_id: ObjectId
