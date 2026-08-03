"""Boundary command: Create a personal Productivity task."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.productivity import CreateTaskInput


@dataclass
class CreateTaskCommand:
    input: CreateTaskInput
