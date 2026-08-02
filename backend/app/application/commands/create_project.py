"""Command (CQRS intent) for creating a Research Project."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.research import CreateProjectInput


@dataclass
class CreateProjectCommand:
    """Intent to register a Research Project (draft → … → closed lifecycle)."""

    input: CreateProjectInput
