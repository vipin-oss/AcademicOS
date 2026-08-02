"""Command (CQRS intent) for adding a project milestone."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.research import MilestoneInput
from app.domain.value_objects.object_id import ObjectId


@dataclass
class AddMilestoneCommand:
    """Intent to add a milestone (BELONGS_TO child) to a project timeline."""

    project_id: ObjectId
    input: MilestoneInput
    actor: str = "system"
