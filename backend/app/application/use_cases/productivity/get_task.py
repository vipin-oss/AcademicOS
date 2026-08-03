"""Use case: Get one personal Productivity task."""
from __future__ import annotations

from app.application.dtos.productivity import TaskOutput
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_task import GetTaskQuery
from app.application.use_cases.productivity.helpers import (
    is_personal_task,
    task_output,
    today_iso,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class GetTaskUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetTaskQuery) -> TaskOutput:
        obj = self._repository.get_by_id(query.object_id)
        if obj is None or obj.object_type is not ObjectType.TASK or not is_personal_task(obj):
            raise ObjectNotFoundError(f"Personal task {query.object_id} not found.")
        return task_output(obj, today_iso())
