"""Use case: Get one Committee — the enriched workspace read.

Mirrors ``GetFacultyUseCase``: type-checked 404 -> base projection with
denormalised PART 7 links -> members resolved + meetings list + stats
(``enrich_committee_output`` — one shared enrichment, no copies).
"""
from __future__ import annotations

from app.application.dtos.committee import COMMITTEE_LINK_GROUPS, CommitteeOutput
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_committee import GetCommitteeQuery
from app.application.use_cases.committees.helpers import enrich_committee_output
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind


class GetCommitteeUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetCommitteeQuery) -> CommitteeOutput:
        obj = self._repository.get_by_id(query.object_id)
        if obj is None or obj.object_type is not ObjectType.COMMITTEE:
            raise ObjectNotFoundError(f"Committee {query.object_id} not found.")

        link_ids = [
            rel.target
            for rel in obj.relationships
            if rel.kind is RelationshipKind.RELATED_TO
        ]
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(link_ids)}
        output = CommitteeOutput.from_domain(obj, [], linked_by_id=linked_by_id)
        output.links = {
            group: output.links.get(group, []) for group in COMMITTEE_LINK_GROUPS
        }
        enrich_committee_output(self._repository, obj, output)
        return output
