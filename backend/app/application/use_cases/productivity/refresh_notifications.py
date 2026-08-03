"""Use case: Reminder-engine sweep — materialise due-work notifications.

Idempotent by construction: candidates carry a deterministic
``source_key``; any existing notification (read, pinned, snoozed or
archived) already holding that key is counted as skipped and never
resurrected. Manual (``generated_by=user``) notifications are untouched.
"""
from __future__ import annotations

from app.application.dtos.productivity import (
    KEY_BODY,
    KEY_CATEGORY,
    KEY_GENERATED_BY,
    KEY_IS_READ,
    KEY_LINK,
    KEY_PRIORITY,
    KEY_SOURCE_KEY,
    KEY_SOURCE_MODULE,
    KEY_SOURCE_REF,
    RefreshNotificationsResult,
)
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.productivity.helpers import (
    ProductivitySnapshot,
    engine_candidates,
    today_iso,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry


class RefreshNotificationsUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, actor: str = "system") -> RefreshNotificationsResult:
        actor = (actor or "system").strip() or "system"
        snapshot = ProductivitySnapshot(self._repository)
        today = today_iso()
        candidates = engine_candidates(snapshot, today)
        existing_keys: set[str] = set()
        for obj in snapshot.notifications:
            key = {entry.key: entry.value for entry in obj.metadata.entries}.get(KEY_SOURCE_KEY)
            if key:
                existing_keys.add(key)

        created = 0
        skipped = 0
        events_all = []
        for candidate in candidates:
            if candidate["source_key"] in existing_keys:
                skipped += 1
                continue
            entries = [
                MetadataEntry(KEY_BODY, str(candidate["body"]), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                MetadataEntry(KEY_CATEGORY, str(candidate["category"]), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                MetadataEntry(KEY_PRIORITY, str(candidate["priority"]), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                MetadataEntry(KEY_SOURCE_MODULE, str(candidate["source_module"]), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                MetadataEntry(KEY_SOURCE_REF, str(candidate["source_ref"]), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                MetadataEntry(KEY_SOURCE_KEY, str(candidate["source_key"]), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                MetadataEntry(KEY_GENERATED_BY, "reminder_engine", MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                MetadataEntry(KEY_IS_READ, "false", MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
            ]
            if candidate.get("link"):
                entries.append(
                    MetadataEntry(KEY_LINK, str(candidate["link"]), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
                )
            obj = UniversalObject.create(
                object_type=ObjectType.NOTIFICATION,
                title=str(candidate["title"]).strip(),
                created_by=actor,
                status=ObjectStatus.ACTIVE,
                metadata=Metadata(entries=tuple(entries)),
            )
            self._repository.save(obj)
            events_all += list(obj.pop_domain_events())
            existing_keys.add(candidate["source_key"])
            created += 1

        if self._event_publisher is not None and events_all:
            self._event_publisher.publish(events_all)
        return RefreshNotificationsResult(
            created=created, skipped_existing=skipped, considered=len(candidates)
        )
