"""Use case: Read one Student (with denormalised links).

Mirrors ``GetPublicationUseCase`` — a non-student Object id (e.g. a Course)
is a 404 at this boundary, not a data leak.
"""
from __future__ import annotations

from app.application.dtos.student import StudentOutput, linked_target_ids
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_student import GetStudentQuery
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class GetStudentUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetStudentQuery) -> StudentOutput:
        obj = self._repository.get_by_id(query.object_id)
        if obj is None or obj.object_type is not ObjectType.STUDENT:
            raise ObjectNotFoundError(f"Student {query.object_id} not found.")
        linked_by_id = {
            str(o.id): o
            for o in self._repository.find_by_ids(linked_target_ids(obj))
        }
        return StudentOutput.from_domain(obj, [], linked_by_id=linked_by_id)
