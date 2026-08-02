"""Boundary command: Delete a Meeting (its action items cascade)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeleteMeetingCommand:
    meeting_id: str
