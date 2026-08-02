"""Boundary command: Delete an Event."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeleteEventCommand:
    object_id: str
