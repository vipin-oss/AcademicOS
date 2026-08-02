"""Use case: Create a Class (course offering).

Mirrors ``CreatePublicationUseCase``: validate -> link targets exist ->
seven-layer metadata record (L6 human-asserted) -> asserted edges
(teachers TAUGHT_BY→faculty, departments BELONGS_TO) -> persist -> events ->
initial enrollment (ENROLLED_IN edges written on the STUDENT objects, so the
roster stays a pure edge query via the frozen interface).
"""
from __future__ import annotations

from app.application.commands.create_class import CreateClassCommand
from app.application.dtos.publication import encode_json_list
from app.application.dtos.teaching import (
    CLASS_GROUP_TO_KIND,
    KEY_CLASS_MODE,
    KEY_COURSE_CODE,
    KEY_CREDITS,
    KEY_NOTES,
    KEY_PROGRAMME,
    KEY_ROOM,
    KEY_SECTION,
    KEY_SEMESTER,
    KEY_SESSION,
    KEY_TAGS,
    KEY_WEEKLY_SCHEDULE,
    ClassOutput,
    encode_json,
)
from app.application.exceptions import ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.teaching.helpers import enrolled_students
from app.application.validators.teaching import assert_valid_create_class_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId


class CreateClassUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: CreateClassCommand) -> ClassOutput:
        data = command.input
        assert_valid_create_class_input(data)

        # Linked Objects (teachers, departments, students) must exist first
        for group, ids in (data.links or {}).items():
            kind = CLASS_GROUP_TO_KIND[group]
            for target_id in ids:
                if target_id == ObjectId("") or not self._repository.exists(target_id):
                    raise ValidationError(f"Linked object {target_id} not found.")
                _ = kind
        for student_id in data.students:
            student = self._repository.get_by_id(student_id)
            if student is None or student.object_type is not ObjectType.STUDENT:
                raise ValidationError(f"Student {student_id} not found.")

        # L6 human-asserted metadata record
        entries: list[MetadataEntry] = []

        def asserted(key: str, value: str) -> None:
            entries.append(
                MetadataEntry(key, value, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
            )

        for key, value in (
            (KEY_COURSE_CODE, (data.course_code or "").strip() or None),
            (KEY_PROGRAMME, data.programme),
            (KEY_SECTION, data.section),
            (KEY_SESSION, data.session),
            (KEY_ROOM, data.room),
            (KEY_CLASS_MODE, data.class_mode),
            (KEY_NOTES, data.notes),
        ):
            if value is not None and str(value) != "":
                asserted(key, str(value))
        if data.semester is not None:
            asserted(KEY_SEMESTER, str(data.semester))
        if data.credits is not None:
            asserted(KEY_CREDITS, str(data.credits))
        if data.weekly_schedule:
            asserted(KEY_WEEKLY_SCHEDULE, encode_json(list(data.weekly_schedule)))
        if data.tags:
            asserted(KEY_TAGS, encode_json_list(data.tags))

        obj = UniversalObject.create(
            object_type=ObjectType.COURSE,
            title=data.title.strip(),
            created_by=data.created_by.strip(),
            status=data.status,
            metadata=Metadata(entries=tuple(entries)),
        )

        for group, ids in (data.links or {}).items():
            for target_id in ids:
                obj.add_relationship(
                    target_id,
                    CLASS_GROUP_TO_KIND[group],
                    Provenance.ASSERTED,
                    actor=data.created_by,
                )

        self._repository.save(obj)

        # Initial enrollment: ENROLLED_IN edges live on the STUDENT objects —
        # the roster is derived by one frozen find_by_type query, no join table.
        for student_id in data.students:
            student = self._repository.get_by_id(student_id)
            assert student is not None  # validated above
            student.add_relationship(
                obj.id, RelationshipKind.ENROLLED_IN, Provenance.ASSERTED,
                actor=data.created_by,
            )
            self._repository.save(student)
            student.pop_domain_events()

        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        all_ids = [oid for ids in (data.links or {}).values() for oid in ids]
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(all_ids)}
        return ClassOutput.from_domain(
            obj,
            events,
            linked_by_id=linked_by_id,
            student_count=len(enrolled_students(self._repository, str(obj.id))),
        )
