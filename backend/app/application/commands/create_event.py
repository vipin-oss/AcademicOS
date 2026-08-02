"""Boundary command: Create an Event."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.events import CreateEventInput


@dataclass
class CreateEventCommand:
    input: CreateEventInput
