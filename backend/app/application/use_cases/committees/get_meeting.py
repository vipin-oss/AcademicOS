"""Use case: Get one Meeting — the enriched meeting-workspace read.

Mirrors the project workspace read: type-checked 404 -> base projection with
the parent committee denormalised -> action items (task children) -> stats.
Supporting-document ids on agenda items and attendee ids are resolved so the
UI never needs a second pass.
"""
from __future__ import annotations

from app.application.dtos.committee import MeetingOutput
from app.application.exceptions import ObjectNotFoundError
from app.application.queries.get_meeting import GetMeetingQuery
from app.application.use_cases.committees.helpers import (
    action_item_output,
    actions_of_meeting,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind


class GetMeetingUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def _committee_of(self, obj: UniversalObject) -> UniversalObject | None:
        for rel in obj.relationships:
            if rel.kind is RelationshipKind.BELONGS_TO:
                target = self._repository.get_by_id(rel.target)
                if target is not None and target.object_type is ObjectType.COMMITTEE:
                    return target
        return None

    def execute(self, query: GetMeetingQuery) -> MeetingOutput:
        obj = self._repository.get_by_id(query.meeting_id)
        if obj is None or obj.object_type is not ObjectType.MEETING:
            raise ObjectNotFoundError(f"Meeting {query.meeting_id} not found.")

        committee = self._committee_of(obj)
        linked = {str(committee.id): committee} if committee else {}
        output = MeetingOutput.from_domain(obj, [], linked_by_id=linked)

        # Resolve supporting documents on agenda items -> [{id, title}].
        document_ids = [
            str(raw)
            for item in output.agenda_items
            for raw in (item.get("document_ids") or [])
        ]
        docs_by_id = {
            str(found.id): found for found in self._repository.find_by_ids(document_ids)
        }
        for item in output.agenda_items:
            item["supporting_documents"] = [
                {"id": str(found.id), "title": found.title}
                for raw in (item.get("document_ids") or [])
                if (found := docs_by_id.get(str(raw))) is not None
            ]

        # Resolve attendee ObjectIds -> names (external names pass through).
        attendee_ids = [
            str(entry.get("object_id"))
            for entry in output.attendance
            if entry.get("object_id")
        ]
        people_by_id = {
            str(found.id): found for found in self._repository.find_by_ids(attendee_ids)
        }
        for entry in output.attendance:
            found = people_by_id.get(str(entry.get("object_id") or ""))
            if found is not None:
                entry["name"] = found.title
                entry["object_type"] = found.object_type.value

        actions = actions_of_meeting(self._repository, str(obj.id))
        output.action_items = [
            action_item_output(action, meeting=obj, committee=committee)
            for action in actions
        ]
        output.stats = {
            "agenda_items": len(output.agenda_items),
            "pending_actions": sum(1 for item in output.action_items if item.status != "done"),
            "completed_actions": sum(1 for item in output.action_items if item.status == "done"),
        }
        return output
