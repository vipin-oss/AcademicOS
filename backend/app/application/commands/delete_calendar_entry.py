"""Boundary command: Delete a personal calendar entry."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeleteCalendarEntryCommand:
    object_id: str
