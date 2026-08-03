"""Use case: Update notification state — read/pin/archive/snooze (PART 4).

Snooze semantics are date-comparison based (no background writes): a
notification is hidden from the default Center while ``snoozed_until`` is
today or in the future, and quietly resurfaces afterwards. ``""`` clears a
snooze. Read/unread maintains the ``read_at`` marker.
"""
from __future__ import annotations

from app.application.commands.update_notification import UpdateNotificationCommand
from app.application.dtos.productivity import (
    KEY_ARCHIVED,
    KEY_BODY,
    KEY_IS_READ,
    KEY_PINNED,
    KEY_SNOOZED_UNTIL,
    NotificationOutput,
)
from app.application.exceptions import ObjectNotFoundError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.productivity.helpers import notification_output, today_iso
from app.application.validators.productivity import assert_valid_update_notification_input
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import MetadataEntry


class UpdateNotificationUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: UpdateNotificationCommand) -> NotificationOutput:
        data = command.input
        assert_valid_update_notification_input(data)

        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.NOTIFICATION:
            raise ObjectNotFoundError(f"Notification {command.object_id} not found.")

        today = today_iso()
        actor = (data.uploaded_by or "system").strip() or "system"

        def write(key: str, value: str) -> None:
            obj.set_metadata(
                MetadataEntry(key, value, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                actor=actor,
            )

        if data.title is not None:
            obj.rename(data.title.strip(), actor=actor)
        if data.body is not None and data.body.strip():
            write(KEY_BODY, data.body)
        if data.is_read is not None:
            write(KEY_IS_READ, "true" if data.is_read else "false")
            write("read_at", today if data.is_read else "")
        if data.pinned is not None:
            write(KEY_PINNED, "true" if data.pinned else "false")
        if data.archived is not None:
            write(KEY_ARCHIVED, "true" if data.archived else "false")
        if data.snoozed_until is not None:
            write(KEY_SNOOZED_UNTIL, data.snoozed_until)  # "" clears the snooze

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return notification_output(obj, today, events)
