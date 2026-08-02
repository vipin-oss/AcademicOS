"""Use case: List the Attendance sessions of a Class (latest first)."""
from __future__ import annotations

from app.application.dtos.teaching import AttendanceSessionOutput
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.list_attendance import ListAttendanceQuery
from app.application.use_cases.teaching.helpers import attendance_sessions_of_class
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class ListAttendanceUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListAttendanceQuery) -> list[AttendanceSessionOutput]:
        cls = self._repository.get_by_id(query.class_id)
        if cls is None or cls.object_type is not ObjectType.COURSE:
            raise ObjectNotFoundError(f"Class {query.class_id} not found.")

        sessions = attendance_sessions_of_class(self._repository, str(cls.id))
        outputs = [AttendanceSessionOutput.from_domain(s, []) for s in sessions]
        outputs.sort(key=lambda out: (out.session_date, out.id), reverse=True)
        return outputs
