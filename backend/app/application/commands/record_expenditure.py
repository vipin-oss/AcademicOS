"""Command (CQRS intent) for recording grant expenditure."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.research import ExpenditureInput
from app.domain.value_objects.object_id import ObjectId


@dataclass
class RecordExpenditureCommand:
    """Intent to record an expenditure entry (BELONGS_TO child) on a grant."""

    grant_id: ObjectId
    input: ExpenditureInput
    actor: str = "system"
