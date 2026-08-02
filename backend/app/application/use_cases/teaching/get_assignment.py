"""Use case: Read one Assignment (owning class denormalised)."""
from __future__ import annotations

from app.application.dtos.teaching import AssignmentOutput
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_assignment import GetAssignmentQuery
from app.application.use_cases.teaching.helpers import class_id_of_assignment
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType
from app.domain.value_objects.object_id import ObjectId


class GetAssignmentUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetAssignmentQuery) -> AssignmentOutput:
        obj = self._repository.get_by_id(query.object_id)
        if obj is None or obj.object_type is not ObjectType.ASSIGNMENT:
            raise ObjectNotFoundError(f"Assignment {query.object_id} not found.")
        class_id = class_id_of_assignment(obj)
        class_obj = (
            self._repository.get_by_id(ObjectId(class_id)) if class_id is not None else None
        )
        return AssignmentOutput.from_domain(obj, [], class_obj=class_obj)
