"""Command (CQRS intent) for updating a Funding Agency."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.research import UpdateAgencyInput
from app.domain.value_objects.object_id import ObjectId


@dataclass
class UpdateAgencyCommand:
    """Intent to update an existing agency (partial; merge semantics)."""

    object_id: ObjectId
    input: UpdateAgencyInput
