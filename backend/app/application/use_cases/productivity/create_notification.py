"""Use case: Create a personal notification (manual notes in the Center)."""
from __future__ import annotations

from app.application.commands.create_notification import CreateNotificationCommand
from app.application.dtos.productivity import (
    KEY_BODY,
    KEY_CATEGORY,
    KEY_GENERATED_BY,
    KEY_IS_READ,
    KEY_LINK,
    KEY_PRIORITY,
    KEY_SOURCE_MODULE,
    KEY_SOURCE_REF,
    NotificationOutput,
)
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.productivity.helpers import notification_output, today_iso
from app.application.validators.productivity import assert_valid_create_notification_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry


class CreateNotificationUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: CreateNotificationCommand) -> NotificationOutput:
        data = command.input
        assert_valid_create_notification_input(data)
        actor = data.uploaded_by.strip()
        entries: list[MetadataEntry] = []

        def put(key: str, value: object) -> None:
            if value is None or str(value) == "":
                return
            entries.append(
                MetadataEntry(key, str(value), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
            )

        put(KEY_BODY, data.body)
        put(KEY_CATEGORY, (data.category or "").strip().lower() or None)
        put(KEY_PRIORITY, (data.priority or "").strip().lower() or None)
        put(KEY_LINK, data.link)
        put(KEY_SOURCE_MODULE, data.source_module or "user")
        put(KEY_SOURCE_REF, data.source_ref)
        put(KEY_GENERATED_BY, "user")
        put(KEY_IS_READ, "false")

        obj = UniversalObject.create(
            object_type=ObjectType.NOTIFICATION,
            title=data.title.strip(),
            created_by=actor,
            status=ObjectStatus.ACTIVE,
            metadata=Metadata(entries=tuple(entries)),
        )
        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return notification_output(obj, today_iso(), events)
