"""Command (CQRS intent) for deleting a grant installment."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class DeleteInstallmentCommand:
    """Intent to delete an installment Object (correction path)."""

    installment_id: ObjectId
