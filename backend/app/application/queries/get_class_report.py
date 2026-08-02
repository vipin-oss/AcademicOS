"""Query (CQRS intent) for the full Class Report (PART K)."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class GetClassReportQuery:
    """Intent to assemble the AI-report-ready Class Report payload."""

    class_id: ObjectId
    attendance_threshold: float = 75.0
