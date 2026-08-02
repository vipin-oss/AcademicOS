"""Use case: Per-student attendance summary of a Class (PART I → J/K).

Computed view — one source of truth: the AttendanceSession Objects and the
roster. Convention (documented, university-norm): a session in which an
enrolled student has NO record counts as ``absent``; ``late`` and
``medical_leave`` still count toward effective presence. The default
threshold is the 75% minimum most Indian universities enforce; the flag
feeds "students below 75% attendance" (PART K) directly.

``build_attendance_summary`` is the shared builder (the class report and
the dashboard reuse it — single implementation, like ``find_duplicates``).
"""
from __future__ import annotations

from app.application.dtos.teaching import (
    ATTENDANCE_STATES,
    KEY_ATTENDANCE_RECORDS,
    AttendanceSummary,
    AttendanceSummaryRow,
    parse_json_object,
)
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_attendance_summary import GetAttendanceSummaryQuery
from app.application.use_cases.teaching.helpers import (
    attendance_sessions_of_class,
    enrolled_students,
    to_roster_entry,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


def build_attendance_summary(
    roster: list[UniversalObject],
    sessions: list[UniversalObject],
    *,
    class_id: str,
    threshold: float,
) -> AttendanceSummary:
    session_records = [
        parse_json_object(s.metadata.get_value(KEY_ATTENDANCE_RECORDS)) for s in sessions
    ]
    rows: list[AttendanceSummaryRow] = []
    for student in roster:
        entry = to_roster_entry(student)
        counts = {state: 0 for state in ATTENDANCE_STATES}
        sid = str(student.id)
        for records in session_records:
            state = records.get(sid, "absent")  # no record -> absent (documented)
            counts[state if state in counts else "absent"] += 1
        total = len(session_records)
        effective = counts["present"] + counts["late"] + counts["medical_leave"]
        percentage = round((effective / total) * 100, 2) if total else 0.0
        rows.append(
            AttendanceSummaryRow(
                student_id=sid,
                student_name=entry.name,
                student_roll=entry.roll_number,
                present=counts["present"],
                absent=counts["absent"],
                late=counts["late"],
                medical_leave=counts["medical_leave"],
                effective_present=effective,
                total=total,
                percentage=percentage,
                below_threshold=bool(total) and percentage < threshold,
            )
        )
    rows.sort(key=lambda r: ((r.student_roll or "￿").casefold(), r.student_name.casefold()))
    return AttendanceSummary(
        class_id=class_id, session_count=len(sessions), threshold=threshold, rows=rows
    )


class GetAttendanceSummaryUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetAttendanceSummaryQuery) -> AttendanceSummary:
        cls = self._repository.get_by_id(query.class_id)
        if cls is None or cls.object_type is not ObjectType.COURSE:
            raise ObjectNotFoundError(f"Class {query.class_id} not found.")
        roster = enrolled_students(self._repository, str(cls.id))
        sessions = attendance_sessions_of_class(self._repository, str(cls.id))
        sessions.sort(key=lambda s: (s.metadata.get_value("session_date") or "", str(s.id)))
        return build_attendance_summary(
            roster, sessions, class_id=str(cls.id), threshold=query.threshold
        )
