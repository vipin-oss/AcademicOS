"""Query (CQRS intent) for reading a single Submission."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class GetSubmissionQuery:
    """Intent to fetch one Submission by Object id."""

    object_id: ObjectId
