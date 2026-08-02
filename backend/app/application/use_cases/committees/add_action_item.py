"""Use case: Add an action item to a Meeting (PART 5).

An action item is a ``task`` Universal Object (BELONGS_TO → the meeting)
carrying assignee/due date/priority/status/progress/completion/remarks as L6
metadata — the installment doctrine verbatim. ``assigned_to`` must resolve to
a FACULTY Object when provided (422); the display name is denormalised so
externals and reports read naturally.
"""
from __future__ import annotations

from app.application.commands.add_action_item import AddActionItemCommand
from app.application.dtos.committee import (
    KEY_ACTION_STATUS,
    KEY_ASSIGNED_NAME,
    KEY_ASSIGNED_TO,
    KEY_COMPLETION_DATE,
    KEY_DUE_DATE,
    KEY_PRIORITY,
    KEY_PROGRESS,
    KEY_REMARKS,
    ActionItemOutput,
)
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.committees.helpers import action_item_output
from app.application.validators.committee import assert_valid_create_action_item_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId


def resolve_assignee(
    repository: ObjectRepository, assigned_to: str | None
) -> tuple[str | None, str | None]:
    """Validate + denormalise the assignee (faculty id -> (id, name))."""
    if not assigned_to or not str(assigned_to).strip():
        return None, None
    target = repository.get_by_id(ObjectId.parse(str(assigned_to).strip()))
    if target is None:
        raise ValidationError(f"Assignee {assigned_to} not found.")
    if target.object_type is not ObjectType.FACULTY:
        raise ValidationError(
            f"assigned_to expects a faculty object; {assigned_to} is a "
            f"{target.object_type.value}."
        )
    return str(target.id), target.title


class AddActionItemUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: AddActionItemCommand) -> ActionItemOutput:
        data = command.input
        assert_valid_create_action_item_input(data)

        meeting = self._repository.get_by_id(command.meeting_id)
        if meeting is None or meeting.object_type is not ObjectType.MEETING:
            raise ObjectNotFoundError(f"Meeting {command.meeting_id} not found.")

        assigned_to, assigned_name = resolve_assignee(self._repository, data.assigned_to)

        actor = (command.actor or "system").strip() or "system"
        entries: list[MetadataEntry] = []

        def put(key: str, value: object) -> None:
            if value is None or str(value) == "":
                return
            entries.append(
                MetadataEntry(
                    key, str(value), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED
                )
            )

        put(KEY_ASSIGNED_TO, assigned_to)
        put(KEY_ASSIGNED_NAME, assigned_name)
        put(KEY_DUE_DATE, data.due_date)
        put(KEY_PRIORITY, (data.priority or "").strip().lower() or None)
        put(KEY_ACTION_STATUS, (data.status or "pending").strip().lower())
        put(KEY_PROGRESS, max(0, min(int(data.progress or 0), 100)))
        put(KEY_COMPLETION_DATE, data.completion_date)
        put(KEY_REMARKS, data.remarks)

        obj = UniversalObject.create(
            object_type=ObjectType.TASK,
            title=data.title.strip(),
            created_by=actor,
            status=ObjectStatus.ACTIVE,
            metadata=Metadata(entries=tuple(entries)),
        )
        obj.add_relationship(
            meeting.id, RelationshipKind.BELONGS_TO, Provenance.ASSERTED, actor=actor
        )
        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return action_item_output(obj, meeting=meeting)
