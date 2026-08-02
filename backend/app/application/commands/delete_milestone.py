"""Command (CQRS intent) for deleting a project milestone."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class DeleteMilestoneCommand:
    """Intent to delete a milestone Object."""

    milestone_id: ObjectId
