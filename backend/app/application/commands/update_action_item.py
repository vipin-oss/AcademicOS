"""Boundary command: Update an action item (partial, merge semantics)."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.committee import UpdateActionItemInput


@dataclass
class UpdateActionItemCommand:
    action_id: str
    input: UpdateActionItemInput
