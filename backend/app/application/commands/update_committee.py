"""Boundary command: Update a Committee (partial, merge semantics)."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.committee import UpdateCommitteeInput


@dataclass
class UpdateCommitteeCommand:
    object_id: str
    input: UpdateCommitteeInput
