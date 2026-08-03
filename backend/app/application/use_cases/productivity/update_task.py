"""Use case: Update a personal Productivity task (verbatim merge semantics).

Mirrors ``UpdateEventUseCase``: validate -> 404 unless the targeted object is
a personal task -> re-check the duplicate guard on the merged result -> L6
metadata merge (absent fields untouched; three-state booleans honoured;
empty strings clear nothing and are never written — the events precedent,
except ``completed=False`` which clears completion via an empty entry) ->
persist -> shaped output.
"""
from __future__ import annotations

import json

from app.application.commands.update_task import UpdateTaskCommand
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
from app.application.exceptions import ObjectAlreadyExistsError, ObjectNotFoundError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.productivity.helpers import (
    is_personal_task,
    personal_tasks,
    task_is_done,
    task_output,
    today_iso,
)
from app.application.validators.productivity import assert_valid_update_task_input
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import MetadataEntry


class UpdateTaskUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: UpdateTaskCommand) -> TaskOutput:
        data = command.input
        assert_valid_update_task_input(data)

        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.TASK or not is_personal_task(obj):
            raise ObjectNotFoundError(f"Personal task {command.object_id} not found.")

        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        merged_title = (data.title.strip() if data.title is not None else obj.title)
        merged_due = (data.due_date or "").strip() if data.due_date is not None else (meta.get(KEY_DUE_DATE) or "")
        for other in personal_tasks(self._repository.find_by_type(ObjectType.TASK)):
            if str(other.id) == str(obj.id):
                continue
            other_meta = {entry.key: entry.value for entry in other.metadata.entries}
            if other.title.casefold() == merged_title.casefold() and (other_meta.get(KEY_DUE_DATE) or "") == merged_due:
                raise ObjectAlreadyExistsError(
                    f"A personal task '{merged_title}' with due date {merged_due or '—'} already exists."
                )

        actor = (data.uploaded_by or "system").strip() or "system"

        def set_if_provided(key: str, value: object) -> None:
            if value is None or str(value) == "":
                return
            obj.set_metadata(
                MetadataEntry(key, str(value), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                actor=actor,
            )

        if data.title is not None:
            obj.rename(merged_title, actor=actor)
        set_if_provided(KEY_DESCRIPTION, data.description)
        set_if_provided(KEY_PRIORITY, data.priority.strip().lower() if data.priority else None)
        set_if_provided(KEY_CATEGORY, data.category.strip().lower() if data.category else None)
        set_if_provided(KEY_START_DATE, data.start_date)
        set_if_provided(KEY_DUE_DATE, data.due_date)
        set_if_provided(KEY_REMINDER, data.reminder)
        if data.tags is not None:
            set_if_provided(KEY_TAGS, json.dumps(data.tags, ensure_ascii=False))
        set_if_provided(KEY_REMARKS, data.remarks)

        if data.pinned is not None:
            obj.set_metadata(
                MetadataEntry(KEY_PINNED, "true" if data.pinned else "false", MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                actor=actor,
            )
        if data.completed is not None:
            was_done = task_is_done(obj)
            obj.set_metadata(
                MetadataEntry(KEY_ACTION_STATUS, "done" if data.completed else "pending", MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                actor=actor,
            )
            if data.completed and not was_done:
                obj.set_metadata(
                    MetadataEntry(KEY_COMPLETION_DATE, today_iso(), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                    actor=actor,
                )
            elif not data.completed:
                obj.set_metadata(
                    MetadataEntry(KEY_COMPLETION_DATE, "", MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                    actor=actor,
                )

        if meta.get(KEY_TASK_SCOPE) != "personal":  # defensive; scope is immutable here
            raise ObjectNotFoundError(f"Personal task {command.object_id} not found.")

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return task_output(obj, today_iso(), events)
