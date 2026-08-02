"""Command (CQRS intent) for creating a Funding Agency."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.research import CreateAgencyInput


@dataclass
class CreateAgencyCommand:
    """Intent to register a Funding Agency (409 on duplicate name)."""

    input: CreateAgencyInput
