"""Use case: Import one date's attendance from CSV (PART I — CSV channel).

Rows (Roll No, Status — headers AND values auto-mapped: P/A/L/ML,
present/absent/…) resolve through the class roster, then record through
the SAME write path as manual entry (``RecordAttendanceUseCase``) — so the
(class, date) upsert and the roster guard live in exactly one place.
Unknown rows are reported; known rows still record.
"""
from __future__ import annotations

from app.application.commands.import_attendance_csv import ImportAttendanceCsvCommand
from app.application.commands.record_attendance import RecordAttendanceCommand
from app.application.dtos.teaching import AttendanceImportResult
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.services import teaching_csv
from app.application.use_cases.teaching.helpers import enrolled_students
from app.application.use_cases.teaching.record_attendance import RecordAttendanceUseCase
from app.application.validators.teaching import validate_session_date
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class ImportAttendanceCsvUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: ImportAttendanceCsvCommand) -> AttendanceImportResult:
        errors = validate_session_date(command.session_date)
        if errors:
            raise ValidationError("; ".join(errors))
        cls = self._repository.get_by_id(command.class_id)
        if cls is None or cls.object_type is not ObjectType.COURSE:
            raise ObjectNotFoundError(f"Class {command.class_id} not found.")
        if not command.text or not command.text.strip():
            raise ValidationError("Nothing to import: the CSV text is empty.")

        rows = teaching_csv.parse_attendance_csv(command.text)
        if not rows:
            raise ValidationError(
                "No attendance rows found — the first CSV row must be a header "
                "(Roll No, Status, …)."
            )

        session_date = command.session_date.strip()
        result = AttendanceImportResult(class_id=str(cls.id), session_date=session_date)
        roster = enrolled_students(self._repository, str(cls.id))
        by_name = {s.title.strip().casefold(): s for s in roster}

        records: dict[str, str] = {}
        for index, record in enumerate(rows):
            roll = (record.get("roll_number") or "").strip()
            state = (record.get("status") or "").strip()
            student = _resolve(roster, roll) or by_name.get(
                (record.get("name") or "").strip().casefold()
            )
            if student is None:
                result.unknown.append(
                    {"index": index, "roll_number": roll, "message": "No roster match."}
                )
                continue
            if not state:
                result.errors.append(
                    {
                        "index": index,
                        "roll_number": roll,
                        "message": "Unknown attendance status; skipped.",
                    }
                )
                continue
            records[str(student.id)] = state

        if records:
            RecordAttendanceUseCase(self._repository, self._event_publisher).execute(
                RecordAttendanceCommand(
                    class_id=cls.id,
                    session_date=session_date,
                    records=records,
                    actor=command.actor,
                )
            )
            result.applied = sorted(records)
        return result


def _resolve(roster, roll: str):
    if not roll:
        return None
    key = roll.casefold()
    for student in roster:
        if (student.metadata.get_value("roll_number") or "").strip().casefold() == key:
            return student
    return None
