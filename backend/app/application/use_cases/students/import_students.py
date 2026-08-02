"""Use case: Bulk-admit Students from a roster CSV (PARTS C + F).

Mirrors ``ImportPublicationsUseCase``: parse with the framework-free
``teaching_csv`` service (header auto-mapping), run registry duplicate
detection per row, create each non-duplicate through the existing
``CreateStudentUseCase`` (single write path). Duplicates are skipped and
reported; malformed rows become per-row errors — the result lists exactly
what was created, skipped, and why.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.application.commands.create_student import CreateStudentCommand
from app.application.dtos.student import CreateStudentInput, ImportStudentsResult
from app.application.exceptions import ApplicationError, ValidationError
from app.application.services import teaching_csv
from app.application.use_cases.students.create_student import (
    CreateStudentUseCase,
    find_duplicates,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectStatus


@dataclass
class ImportStudentsCommand:
    """Intent to import roster CSV text."""

    text: str
    created_by: str


def _to_create_input(record: dict, created_by: str) -> CreateStudentInput:
    """Map a canonicalised CSV row onto the create boundary DTO."""
    student_type = (record.get("student_type") or "ug").strip().lower()
    if student_type not in ("ug", "pg", "phd", "alumni"):
        student_type = "ug"

    def as_int(value) -> int | None:
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    return CreateStudentInput(
        name=str(record.get("name") or "").strip(),
        created_by=created_by,
        student_type=student_type,
        status=ObjectStatus.ACTIVE,
        roll_number=record.get("roll_number"),
        registration_number=record.get("registration_number"),
        university_enrollment=record.get("university_enrollment"),
        email=record.get("email"),
        phone=record.get("phone"),
        programme=record.get("programme"),
        department=record.get("department"),
        semester=as_int(record.get("semester")),
        section=record.get("section"),
        batch=record.get("batch"),
        admission_date=record.get("admission_date"),
        expected_graduation=record.get("expected_graduation"),
        research_area=record.get("research_area"),
        orcid=record.get("orcid"),
        google_scholar=record.get("google_scholar"),
        notes=record.get("notes"),
        tags=tuple(
            tag.strip()
            for tag in (record.get("tags") or "").replace(",", ";").split(";")
            if tag.strip()
        ),
        links=None,
    )


class ImportStudentsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, command: ImportStudentsCommand) -> ImportStudentsResult:
        if not command.text or not command.text.strip():
            raise ValidationError("Nothing to import: the CSV text is empty.")
        if not command.created_by or not command.created_by.strip():
            raise ValidationError("created_by must identify an actor.")

        rows = teaching_csv.parse_students_csv(command.text)
        if not rows:
            raise ValidationError(
                "No student rows found — the first CSV row must be a header "
                "(Roll No, Name, Email, …)."
            )

        result = ImportStudentsResult()
        creator = CreateStudentUseCase(self._repository)

        for index, record in enumerate(rows):
            name = str(record.get("name") or "").strip()
            roll = str(record.get("roll_number") or "").strip()
            if not name or not roll:
                result.errors.append(
                    {
                        "index": index,
                        "message": "Row needs at least a Name and a Roll No; skipped.",
                    }
                )
                continue
            if find_duplicates(
                self._repository,
                roll_number=roll,
                university_enrollment=record.get("university_enrollment"),
            ):
                result.skipped_duplicates.append(
                    {
                        "index": index,
                        "name": name,
                        "roll_number": roll,
                        "message": "Already exists (roll number or enrollment id).",
                    }
                )
                continue
            try:
                out = creator.execute(
                    CreateStudentCommand(input=_to_create_input(record, command.created_by))
                )
                result.created.append(out.id)
            except ApplicationError as exc:  # surface per-row, keep importing the rest
                result.errors.append({"index": index, "name": name, "message": str(exc)})
        return result
