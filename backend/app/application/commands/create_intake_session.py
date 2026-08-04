"""Command (CQRS intent) for creating an Intake Session."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.intake import CreateIntakeSessionInput


@dataclass
class CreateIntakeSessionCommand:
    """Intent to start one import operation (folder or explicit files)."""

    input: CreateIntakeSessionInput
