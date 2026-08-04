"""Command (CQRS intent) for deleting an Intake Session."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeleteIntakeSessionCommand:
    """Intent to delete a session with its items and staged blobs."""

    session_id: str
