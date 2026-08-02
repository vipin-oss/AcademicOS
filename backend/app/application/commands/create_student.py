"""Command (CQRS intent) for registering a Student."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.student import CreateStudentInput


@dataclass
class CreateStudentCommand:
    """Intent to admit a Student (manual entry / CSV import)."""

    input: CreateStudentInput
