"""Boundary command: Update a personal Productivity task (merge semantics)."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.productivity import UpdateTaskInput


@dataclass
class UpdateTaskCommand:
    object_id: str
    input: UpdateTaskInput
