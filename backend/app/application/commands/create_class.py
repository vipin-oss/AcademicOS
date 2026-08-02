"""Command (CQRS intent) for creating a Class."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.teaching import CreateClassInput


@dataclass
class CreateClassCommand:
    """Intent to create a Class (course offering)."""

    input: CreateClassInput
