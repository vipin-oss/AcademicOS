"""Use case: Get one Purchase Proposal — the enriched workspace read.

Mirrors ``GetCommitteeUseCase``: type-checked 404 -> base projection with
denormalised link groups -> one shared enrichment (resolved vendors,
supporting documents, approval meeting, stats).
"""
from __future__ import annotations

from app.application.dtos.finance import ProposalOutput
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_proposal import GetProposalQuery
from app.application.use_cases.finance.helpers import enrich_proposal_output
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind


class GetProposalUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetProposalQuery) -> ProposalOutput:
        obj = self._repository.get_by_id(query.object_id)
        if obj is None or obj.object_type is not ObjectType.PURCHASE:
            raise ObjectNotFoundError(f"Purchase proposal {query.object_id} not found.")

        link_ids = [
            rel.target
            for rel in obj.relationships
            if rel.kind is RelationshipKind.RELATED_TO
        ]
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(link_ids)}
        output = ProposalOutput.from_domain(obj, [], linked_by_id=linked_by_id)
        enrich_proposal_output(self._repository, obj, output)
        return output
