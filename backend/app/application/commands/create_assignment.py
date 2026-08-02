"""Command (CQRS intent) for creating an Assignment in a Class."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.teaching import CreateAssignmentInput


@dataclass
class CreateAssignmentCommand:
    """Intent to create an Assignment (assessment) inside a Class."""

    input: CreateAssignmentInput
