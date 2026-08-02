"""Use case: Read one Grant (enriched: installments, expenditures, budget).

One read feeds the whole grant workspace: registry fields, linked projects
and agency, installment schedule (number order), expenditure ledger (date
order) and the computed PART 7 budget (approved/released/utilized/remaining).
"""
from __future__ import annotations

from app.application.dtos.research import GrantOutput, linked_target_ids
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_grant import GetGrantQuery
from app.application.use_cases.research.helpers import (
    expenditure_output,
    expenditures_of_grant,
    grant_totals,
    installment_output,
    installments_of_grant,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType


class GetGrantUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetGrantQuery) -> GrantOutput:
        obj = self._repository.get_by_id(query.object_id)
        if obj is None or obj.object_type is not ObjectType.GRANT:
            raise ObjectNotFoundError(f"Grant {query.object_id} not found.")

        grant_id = str(obj.id)
        linked_by_id = {
            str(o.id): o for o in self._repository.find_by_ids(linked_target_ids(obj))
        }
        out = GrantOutput.from_domain(obj, [], linked_by_id=linked_by_id)
        out.installments = [
            installment_output(i) for i in installments_of_grant(self._repository, grant_id)
        ]
        out.expenditures = [
            expenditure_output(e) for e in expenditures_of_grant(self._repository, grant_id)
        ]
        out.budget = grant_totals(self._repository, obj)
        return out
