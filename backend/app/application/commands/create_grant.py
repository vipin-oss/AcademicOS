"""Command (CQRS intent) for creating a Grant."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.research import CreateGrantInput


@dataclass
class CreateGrantCommand:
    """Intent to register a Grant (409 on duplicate grant number)."""

    input: CreateGrantInput
