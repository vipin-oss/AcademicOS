"""Command (CQRS intent) for registering a Faculty member."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.faculty import CreateFacultyInput


@dataclass
class CreateFacultyCommand:
    """Intent to register a Faculty member (409 on duplicate employee id / faculty code)."""

    input: CreateFacultyInput
