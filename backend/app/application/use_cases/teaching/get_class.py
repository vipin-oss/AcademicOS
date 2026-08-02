"""Use case: Read one Class (with teachers/departments denormalised)."""
from __future__ import annotations

from app.application.dtos.teaching import ClassOutput
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_class import GetClassQuery
from app.application.use_cases.teaching.helpers import enrolled_students
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class GetClassUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetClassQuery) -> ClassOutput:
        obj = self._repository.get_by_id(query.object_id)
        if obj is None or obj.object_type is not ObjectType.COURSE:
            raise ObjectNotFoundError(f"Class {query.object_id} not found.")
        linked_by_id = {
            str(o.id): o
            for o in self._repository.find_by_ids(
                [r.target for r in obj.relationships]
            )
        }
        return ClassOutput.from_domain(
            obj,
            [],
            linked_by_id=linked_by_id,
            student_count=len(enrolled_students(self._repository, str(obj.id))),
        )
