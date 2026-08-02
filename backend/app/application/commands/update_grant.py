"""Command (CQRS intent) for updating a Grant."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.research import UpdateGrantInput
from app.domain.value_objects.object_id import ObjectId


@dataclass
class UpdateGrantCommand:
    """Intent to update an existing grant (partial; merge semantics)."""

    object_id: ObjectId
    input: UpdateGrantInput
