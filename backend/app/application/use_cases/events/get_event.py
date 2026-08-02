"""Use case: Get one Event — the enriched workspace read.

Mirrors ``GetProposalUseCase``: type-checked 404 -> base projection with
denormalised link groups -> one shared enrichment (resolved
document/publication/speaker refs, stats).
"""
from __future__ import annotations

from app.application.dtos.events import EventOutput
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_event import GetEventQuery
from app.application.use_cases.events.helpers import enrich_event_output
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind


class GetEventUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: GetEventQuery) -> EventOutput:
        obj = self._repository.get_by_id(query.object_id)
        if obj is None or obj.object_type is not ObjectType.EVENT:
            raise ObjectNotFoundError(f"Event {query.object_id} not found.")

        link_ids = [
            rel.target
            for rel in obj.relationships
            if rel.kind is RelationshipKind.RELATED_TO
        ]
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(link_ids)}
        output = EventOutput.from_domain(obj, [], linked_by_id=linked_by_id)
        enrich_event_output(self._repository, obj, output)
        return output
