"""Boundary command: Delete a Committee (meetings + action items cascade)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeleteCommitteeCommand:
    object_id: str
