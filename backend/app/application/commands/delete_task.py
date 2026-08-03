"""Boundary command: Delete a personal Productivity task."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeleteTaskCommand:
    object_id: str
