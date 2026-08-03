"""Use case: Create a personal Productivity task.

Mirrors ``CreateEventUseCase``: validate -> duplicate scan (same title with
the same due date, 409) -> L6 human-asserted metadata record (no committee
``BELONGS_TO`` edge — disjoint from committee actions by construction) ->
persist -> events -> shaped output (one shared shaper, no copies).
"""
from __future__ import annotations

import json

from app.application.commands.create_task import CreateTaskCommand
from app.application.dtos.productivity import (
    KEY_ACTION_STATUS,
    KEY_CATEGORY,
    KEY_COMPLETION_DATE,
    KEY_DESCRIPTION,
    KEY_DUE_DATE,
    KEY_PINNED,
    KEY_PRIORITY,
    KEY_REMARKS,
    KEY_REMINDER,
    KEY_START_DATE,
    KEY_TAGS,
    KEY_TASK_SCOPE,
    TaskOutput,
)
from app.application.exceptions import ObjectAlreadyExistsError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.productivity.helpers import (
    personal_tasks,
    task_output,
    today_iso,
)
from app.application.validators.productivity import assert_valid_create_task_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectStatus,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry


class CreateTaskUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: CreateTaskCommand) -> TaskOutput:
        data = command.input
        assert_valid_create_task_input(data)

        all_tasks = self._repository.find_by_type(ObjectType.TASK)
        title_cf = data.title.strip().casefold()
        due = (data.due_date or "").strip()
        for existing in personal_tasks(all_tasks):
            other = {entry.key: entry.value for entry in existing.metadata.entries}
            if existing.title.casefold() == title_cf and (other.get(KEY_DUE_DATE) or "") == due:
                raise ObjectAlreadyExistsError(
                    f"A personal task '{data.title.strip()}' with due date {due or '—'} already exists."
                )

        actor = data.uploaded_by.strip()
        entries: list[MetadataEntry] = []

        def put(key: str, value: object) -> None:
            if value is None or str(value) == "":
                return
            entries.append(
                MetadataEntry(key, str(value), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
            )

        put(KEY_TASK_SCOPE, "personal")
        put(KEY_DESCRIPTION, data.description)
        put(KEY_PRIORITY, (data.priority or "").strip().lower() or None)
        put(KEY_CATEGORY, (data.category or "").strip().lower() or None)
        put(KEY_START_DATE, data.start_date)
        put(KEY_DUE_DATE, data.due_date)
        put(KEY_ACTION_STATUS, "done" if data.completed else "pending")
        if data.completed:
            put(KEY_COMPLETION_DATE, today_iso())
        put(KEY_PINNED, "true" if data.pinned else None)
        put(KEY_REMINDER, data.reminder)
        put(KEY_TAGS, json.dumps(data.tags, ensure_ascii=False) if data.tags else None)
        put(KEY_REMARKS, data.remarks)

        obj = UniversalObject.create(
            object_type=ObjectType.TASK,
            title=data.title.strip(),
            created_by=actor,
            status=ObjectStatus.ACTIVE,
            metadata=Metadata(entries=tuple(entries)),
        )
        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return task_output(obj, today_iso(), events)
