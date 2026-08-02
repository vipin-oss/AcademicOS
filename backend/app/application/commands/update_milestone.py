"""Command (CQRS intent) for updating a project milestone."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.research import UpdateMilestoneInput
from app.domain.value_objects.object_id import ObjectId


@dataclass
class UpdateMilestoneCommand:
    """Intent to update a milestone (title/date/status/notes; partial)."""

    milestone_id: ObjectId
    input: UpdateMilestoneInput
