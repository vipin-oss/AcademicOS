"""Boundary command: Update a Meeting (partial, merge semantics)."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.committee import UpdateMeetingInput


@dataclass
class UpdateMeetingCommand:
    meeting_id: str
    input: UpdateMeetingInput
