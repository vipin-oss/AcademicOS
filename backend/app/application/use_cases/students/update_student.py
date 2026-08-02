"""Use case: Update a Student (partial; metadata + link groups).

Mirrors ``UpdatePublicationUseCase``: every mutation goes through its
dedicated aggregate method so versioning, audit and domain events stay
intact; link groups merge per group (present group replaces, absent
untouched); registry duplicate detection re-runs when the roll number,
enrollment id or name changes (excluding the Object itself).
"""
from __future__ import annotations

from app.application.commands.update_student import UpdateStudentCommand
from app.application.dtos.publication import encode_json_list
from app.application.dtos.student import (
    GROUP_TO_KIND,
    KEY_ADMISSION_DATE,
    KEY_BATCH,
    KEY_DEPARTMENT,
    KEY_EMAIL,
    KEY_EXPECTED_GRADUATION,
    KEY_GOOGLE_SCHOLAR,
    KEY_NOTES,
    KEY_ORCID,
    KEY_PHONE,
    KEY_PROGRAMME,
    KEY_REGISTRATION_NUMBER,
    KEY_RESEARCH_AREA,
    KEY_ROLL_NUMBER,
    KEY_SECTION,
    KEY_SEMESTER,
    KEY_STUDENT_TYPE,
    KEY_TAGS,
    KEY_UNIVERSITY_ENROLLMENT,
    StudentOutput,
    edge_group,
    linked_target_ids,
)
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.students.create_student import find_duplicates
from app.application.validators.student import assert_valid_update_student_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import MetadataEntry


class UpdateStudentUseCase:
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

    def execute(self, command: UpdateStudentCommand) -> StudentOutput:
        data = command.input
        assert_valid_update_student_input(data)

        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.STUDENT:
            raise ObjectNotFoundError(f"Student {command.object_id} not found.")

        actor = data.actor.strip()

        # --- duplicate detection when identity fields change -------------
        if (data.roll_number is not None and data.roll_number.strip() != (obj.metadata.get_value(KEY_ROLL_NUMBER) or "")) or (
            data.university_enrollment is not None
            and data.university_enrollment != obj.metadata.get_value(KEY_UNIVERSITY_ENROLLMENT)
        ):
            dupes = find_duplicates(
                self._repository,
                roll_number=(
                    data.roll_number if data.roll_number is not None
                    else obj.metadata.get_value(KEY_ROLL_NUMBER)
                ),
                university_enrollment=(
                    data.university_enrollment if data.university_enrollment is not None
                    else obj.metadata.get_value(KEY_UNIVERSITY_ENROLLMENT)
                ),
                exclude_id=str(obj.id),
            )
            if dupes:
                raise ObjectAlreadyExistsError(
                    f"Duplicate student: {dupes[0].id} ({dupes[0].title!r}) already has "
                    f"this roll number or enrollment id."
                )

        # --- link groups (validate first, then merge per group) ----------
        if data.links is not None:
            for group, ids in data.links.items():
                kind = GROUP_TO_KIND[group]
                wanted = {str(oid) for oid in ids}
                for oid in ids:
                    if oid == obj.id:
                        raise ValidationError("A student cannot be linked to itself.")
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

        # --- name / lifecycle --------------------------------------------
        if data.name is not None and data.name.strip() != obj.title:
            obj.rename(data.name, actor)
        if data.status is not None and data.status != obj.status:
            obj.change_status(data.status, actor)

        # --- human-asserted metadata (L6) ---------------------------------
        scalar_fields = (
            (KEY_STUDENT_TYPE, data.student_type),
            (KEY_ROLL_NUMBER, data.roll_number.strip() if data.roll_number else None),
            (KEY_REGISTRATION_NUMBER, data.registration_number),
            (KEY_UNIVERSITY_ENROLLMENT, data.university_enrollment),
            (KEY_EMAIL, data.email),
            (KEY_PHONE, data.phone),
            (KEY_PROGRAMME, data.programme),
            (KEY_DEPARTMENT, data.department),
            (KEY_SECTION, data.section),
            (KEY_BATCH, data.batch),
            (KEY_ADMISSION_DATE, data.admission_date),
            (KEY_EXPECTED_GRADUATION, data.expected_graduation),
            (KEY_RESEARCH_AREA, data.research_area),
            (KEY_ORCID, data.orcid),
            (KEY_GOOGLE_SCHOLAR, data.google_scholar),
            (KEY_NOTES, data.notes),
        )
        for key, value in scalar_fields:
            if value is not None:
                self._assert(obj, key, str(value), actor)
        if data.semester is not None:
            self._assert(obj, KEY_SEMESTER, str(data.semester), actor)
        if data.tags is not None:
            self._assert(obj, KEY_TAGS, encode_json_list(data.tags), actor)

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        linked_by_id = {
            str(o.id): o for o in self._repository.find_by_ids(linked_target_ids(obj))
        }
        return StudentOutput.from_domain(obj, events, linked_by_id=linked_by_id)

    def _group_of(self, rel_kind, target) -> str | None:
        linked = self._repository.get_by_id(target)
        if linked is None:
            return None
        return edge_group(rel_kind, linked.object_type)
