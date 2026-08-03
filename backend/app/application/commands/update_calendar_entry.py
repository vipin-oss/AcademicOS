"""Boundary command: Update a personal calendar entry (merge semantics)."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.productivity import UpdateEntryInput


@dataclass
class UpdateCalendarEntryCommand:
    object_id: str
    input: UpdateEntryInput
