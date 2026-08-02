"""Command (CQRS intent) for logging a project progress update."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.research import ProgressUpdateInput
from app.domain.value_objects.object_id import ObjectId


@dataclass
class RecordProgressUpdateCommand:
    """Intent to append {date, percent, remark} to the project timeline."""

    project_id: ObjectId
    input: ProgressUpdateInput
    actor: str = "system"
