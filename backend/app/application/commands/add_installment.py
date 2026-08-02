"""Command (CQRS intent) for recording a grant installment."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.research import InstallmentInput
from app.domain.value_objects.object_id import ObjectId


@dataclass
class AddInstallmentCommand:
    """Intent to record a release installment (BELONGS_TO child) on a grant."""

    grant_id: ObjectId
    input: InstallmentInput
    actor: str = "system"
