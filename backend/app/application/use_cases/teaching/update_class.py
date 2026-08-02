"""Use case: Update a Class (partial; metadata + link groups).

Mirrors ``UpdateStudentUseCase`` / ``UpdatePublicationUseCase``: every
mutation goes through its dedicated aggregate method so versioning, audit
and domain events stay intact; link groups merge per group (a group present
in ``links`` replaces exactly that group; absent groups are untouched).
Enrollment is NOT edited here — it has its own commands (PART C).
"""
from __future__ import annotations

from app.application.commands.update_class import UpdateClassCommand
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
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.teaching.helpers import enrolled_students
from app.application.validators.teaching import assert_valid_update_class_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import MetadataEntry


class UpdateClassUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def _assert(self, obj: UniversalObject, key: str, value: str, actor: str) -> None:
        if obj.metadata.get_value(key) != value:
            obj.set_metadata(
                MetadataEntry(key, value, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                actor=actor,
            )

    def execute(self, command: UpdateClassCommand) -> ClassOutput:
        data = command.input
        assert_valid_update_class_input(data)

        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.COURSE:
            raise ObjectNotFoundError(f"Class {command.object_id} not found.")

        actor = data.actor.strip()

        # --- link groups (validate first, then merge per group) ----------
        if data.links is not None:
            for group, ids in data.links.items():
                kind = CLASS_GROUP_TO_KIND[group]
                wanted = {str(oid) for oid in ids}
                for oid in ids:
                    if oid == obj.id:
                        raise ValidationError("A class cannot be linked to itself.")
                    if not self._repository.exists(oid):
                        raise ValidationError(f"Linked object {oid} not found.")
                current = [r.target for r in obj.relationships if r.kind == kind]
                for target in current:
                    if str(target) not in wanted and self._group_of(kind, target) == group:
                        obj.remove_relationship(target, kind, Provenance.ASSERTED, actor=actor)
                present = {str(r.target) for r in obj.relationships if r.kind == kind}
                for oid in ids:
                    if str(oid) not in present:
                        obj.add_relationship(oid, kind, Provenance.ASSERTED, actor=actor)

        # --- title / lifecycle -------------------------------------------
        if data.title is not None and data.title.strip() != obj.title:
            obj.rename(data.title, actor)
        if data.status is not None and data.status != obj.status:
            obj.change_status(data.status, actor)

        # --- human-asserted metadata (L6) ---------------------------------
        scalar_fields = (
            (KEY_COURSE_CODE, data.course_code.strip() if data.course_code else None),
            (KEY_PROGRAMME, data.programme),
            (KEY_SECTION, data.section),
            (KEY_SESSION, data.session),
            (KEY_ROOM, data.room),
            (KEY_CLASS_MODE, data.class_mode),
            (KEY_NOTES, data.notes),
        )
        for key, value in scalar_fields:
            if value is not None:
                self._assert(obj, key, str(value), actor)
        if data.semester is not None:
            self._assert(obj, KEY_SEMESTER, str(data.semester), actor)
        if data.credits is not None:
            self._assert(obj, KEY_CREDITS, str(data.credits), actor)
        if data.weekly_schedule is not None:
            self._assert(obj, KEY_WEEKLY_SCHEDULE, encode_json(list(data.weekly_schedule)), actor)
        if data.tags is not None:
            self._assert(obj, KEY_TAGS, encode_json_list(data.tags), actor)

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        linked_by_id = {
            str(o.id): o
            for o in self._repository.find_by_ids([r.target for r in obj.relationships])
        }
        return ClassOutput.from_domain(
            obj,
            events,
            linked_by_id=linked_by_id,
            student_count=len(enrolled_students(self._repository, str(obj.id))),
        )

    def _group_of(self, rel_kind, target) -> str | None:
        if rel_kind is RelationshipKind.TAUGHT_BY:
            linked = self._repository.get_by_id(target)
            if linked is not None and linked.object_type is ObjectType.FACULTY:
                return "teachers"
            return None
        if rel_kind is RelationshipKind.BELONGS_TO:
            return "departments"
        return None
