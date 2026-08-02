"""Query (CQRS intent) for the per-student attendance summary (PART I)."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class GetAttendanceSummaryQuery:
    """Intent to compute per-student attendance percentages for one Class.

    ``threshold`` is the university minimum (default 75%): students below it
    are flagged for the dashboard / AI reports.
    """

    class_id: ObjectId
    threshold: float = 75.0
