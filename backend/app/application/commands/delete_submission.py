"""Command (CQRS intent) for deleting a Submission."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class DeleteSubmissionCommand:
    """Intent to delete a Submission (faculty correction; blob included)."""

    object_id: ObjectId
