"""Use case: Bulk-enroll from a roster CSV (PARTS C + F).

Parses the CSV with the framework-free ``teaching_csv`` service (header
auto-mapping), resolves each row to an EXISTING student (roll number first,
e-mail fallback — portable scans over the frozen repository), then enrolls
through the single write path (``EnrollStudentsUseCase``). Rows without a
match become per-row errors; the rest still enrolls.
"""
from __future__ import annotations

from app.application.commands.enroll_from_csv import EnrollFromCsvCommand
from app.application.commands.enroll_students import EnrollStudentsCommand
from app.application.dtos.student import KEY_EMAIL, KEY_ROLL_NUMBER
from app.application.dtos.teaching import EnrollmentResult
from app.application.exceptions import ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.services import teaching_csv
from app.application.use_cases.teaching.enroll_students import EnrollStudentsUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


def _resolve_student(
    students: list[UniversalObject], *, roll: str, email: str
) -> UniversalObject | None:
    """Roll number (case-insensitive) first, e-mail fallback."""
    roll_key = roll.strip().casefold()
    email_key = email.strip().casefold()
    for student in students:
        if roll_key and (
            (student.metadata.get_value(KEY_ROLL_NUMBER) or "").strip().casefold() == roll_key
        ):
            return student
    if email_key:
        for student in students:
            if (student.metadata.get_value(KEY_EMAIL) or "").strip().casefold() == email_key:
                return student
    return None


class EnrollFromCsvUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: EnrollFromCsvCommand) -> EnrollmentResult:
        if not command.text or not command.text.strip():
            raise ValidationError("Nothing to import: the CSV text is empty.")

        rows = teaching_csv.parse_roster_csv(command.text)
        if not rows:
            raise ValidationError(
                "No enrollment rows found — the first CSV row must be a header "
                "(Roll No, Email, …)."
            )

        students = self._repository.find_by_type(ObjectType.STUDENT)
        ids = []
        result = EnrollmentResult()
        for index, record in enumerate(rows):
            roll = record.get("roll_number", "")
            email = record.get("email", "")
            student = _resolve_student(students, roll=roll, email=email)
            if student is None:
                result.errors.append(
                    {
                        "index": index,
                        "roll_number": roll,
                        "email": email,
                        "message": "No student matches this row; admit them first.",
                    }
                )
                continue
            ids.append(student.id)

        if ids:
            enrolled = EnrollStudentsUseCase(self._repository, self._event_publisher).execute(
                EnrollStudentsCommand(
                    class_id=command.class_id,
                    student_ids=tuple(ids),
                    actor=command.actor,
                )
            )
            result.enrolled = enrolled.enrolled
            result.already_enrolled = enrolled.already_enrolled
            result.errors.extend(enrolled.errors)
        return result
