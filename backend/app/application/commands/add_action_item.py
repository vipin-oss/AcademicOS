"""Boundary command: Add an action item to a Meeting (PART 5)."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.committee import CreateActionItemInput


@dataclass
class AddActionItemCommand:
    meeting_id: str
    input: CreateActionItemInput
    actor: str
