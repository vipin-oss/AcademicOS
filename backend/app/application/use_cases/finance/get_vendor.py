"""Use case: Get one Vendor (registry row + computed stats)."""
from __future__ import annotations

from app.application.dtos.finance import VendorOutput
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_vendor import GetVendorQuery
from app.application.use_cases.finance.helpers import vendor_stats
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class GetVendorUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetVendorQuery) -> VendorOutput:
        obj = self._repository.get_by_id(query.object_id)
        if obj is None or obj.object_type is not ObjectType.VENDOR:
            raise ObjectNotFoundError(f"Vendor {query.object_id} not found.")
        output = VendorOutput.from_domain(obj, [])
        output.stats = vendor_stats(self._repository, str(obj.id))
        return output
