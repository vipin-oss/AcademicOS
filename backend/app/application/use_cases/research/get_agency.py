"""Use case: Read one Funding Agency."""
from __future__ import annotations

from app.application.dtos.research import AgencyOutput
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_agency import GetAgencyQuery
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class GetAgencyUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetAgencyQuery) -> AgencyOutput:
        obj = self._repository.get_by_id(query.object_id)
        if obj is None or obj.object_type is not ObjectType.FUNDING_AGENCY:
            raise ObjectNotFoundError(f"Funding agency {query.object_id} not found.")
        return AgencyOutput.from_domain(obj, [])
