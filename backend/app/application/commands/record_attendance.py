"""Command (CQRS intent) for recording an Attendance session."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class RecordAttendanceCommand:
    """Intent to record attendance for a Class on one date (upsert).

    One AttendanceSession Object per (class, date); re-recording the same
    date updates the same Object — no duplicates."""

    class_id: ObjectId
    session_date: str  # YYYY-MM-DD
    records: dict  # {student_id: present|absent|late|medical_leave}
    actor: str = "system"
