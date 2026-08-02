"""Command (CQRS intent) for importing attendance from a CSV."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class ImportAttendanceCsvCommand:
    """Intent to record one Class date's attendance from CSV text (PART I).

    Rows map (Roll No, Status) through the roster into the upserted
    AttendanceSession Object for (class, date) — the same write path as
    manual entry.
    """

    class_id: ObjectId
    session_date: str  # YYYY-MM-DD
    text: str
    actor: str = "system"
