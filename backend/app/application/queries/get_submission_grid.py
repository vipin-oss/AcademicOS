"""Query (CQRS intent) for the student × assignment submission grid."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class GetSubmissionGridQuery:
    """Intent to compute the roster × submission matrix of one Assignment
    (UI Spec §2.5 C7): every enrolled student gets a row, pending included."""

    assignment_id: ObjectId
