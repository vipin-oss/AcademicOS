"""Boundary command: Create a personal calendar entry."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.productivity import CreateEntryInput


@dataclass
class CreateCalendarEntryCommand:
    input: CreateEntryInput
