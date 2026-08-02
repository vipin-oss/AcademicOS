"""Boundary command: Add a Meeting to a Committee (PART 3)."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.committee import CreateMeetingInput


@dataclass
class AddMeetingCommand:
    committee_id: str
    input: CreateMeetingInput
    actor: str
