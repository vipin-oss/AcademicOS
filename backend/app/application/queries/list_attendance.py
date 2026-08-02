"""Query (CQRS intent) for listing Attendance sessions of a Class."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects.object_id import ObjectId


@dataclass
class ListAttendanceQuery:
    """Intent to list the AttendanceSession Objects of one Class."""

    class_id: ObjectId
