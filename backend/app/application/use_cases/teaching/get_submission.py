"""Use case: Read one Submission (student denormalised)."""
from __future__ import annotations

from app.application.dtos.teaching import SubmissionOutput
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_submission import GetSubmissionQuery
from app.application.use_cases.teaching.helpers import student_of_submission
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class GetSubmissionUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetSubmissionQuery) -> SubmissionOutput:
        obj = self._repository.get_by_id(query.object_id)
        if obj is None or obj.object_type is not ObjectType.SUBMISSION:
            raise ObjectNotFoundError(f"Submission {query.object_id} not found.")
        student_id = student_of_submission(obj)
        student = (
            self._repository.get_by_id(student_id) if student_id is not None else None
        )
        return SubmissionOutput.from_domain(obj, [], student=student)
