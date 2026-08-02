"""Boundary command: Update an Event (partial, merge semantics)."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.events import UpdateEventInput


@dataclass
class UpdateEventCommand:
    object_id: str
    input: UpdateEventInput
