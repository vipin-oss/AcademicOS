"""Boundary command: Delete an action item."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeleteActionItemCommand:
    action_id: str
