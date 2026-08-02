"""Use case: Admit a Student (manual entry / CSV import row).

Mirrors ``CreatePublicationUseCase``: validate -> duplicate check (roll no /
university enrollment, portable across engines) -> build the seven-layer
metadata record (every registry field is L6 human-asserted) -> asserted
supervision/project/grant/… edges -> persist -> events -> output.
"""
from __future__ import annotations

from app.application.commands.create_student import CreateStudentCommand
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
)
from app.application.exceptions import ObjectAlreadyExistsError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.validators.student import assert_valid_create_student_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId


def find_duplicates(
    repository: ObjectRepository,
    *,
    roll_number: str | None,
    university_enrollment: str | None,
    exclude_id: str | None = None,
) -> list[UniversalObject]:
    """Registry duplicate detection: roll number or enrollment id.

    Evaluated in Python over ``find_by_type`` (frozen interface), identical
    on PostgreSQL, SQLite and in-memory repositories — no JSONB dependency.
    Roll numbers compare case-insensitively; enrollment ids compare exactly.
    """
    matches: list[UniversalObject] = []
    roll = (roll_number or "").strip().casefold()
    enrollment = (university_enrollment or "").strip()
    if not roll and not enrollment:
        return matches
    for student in repository.find_by_type(ObjectType.STUDENT):
        if exclude_id is not None and str(student.id) == exclude_id:
            continue
        existing_roll = (student.metadata.get_value(KEY_ROLL_NUMBER) or "").strip().casefold()
        existing_enroll = (student.metadata.get_value(KEY_UNIVERSITY_ENROLLMENT) or "").strip()
        if roll and existing_roll == roll:
            matches.append(student)
        elif enrollment and existing_enroll == enrollment:
            matches.append(student)
    return matches


class CreateStudentUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: CreateStudentCommand) -> StudentOutput:
        data = command.input

        # 1. Validate boundary input
        assert_valid_create_student_input(data)

        # 2. Registry duplicate detection (roll no / enrollment) -> 409
        duplicates = find_duplicates(
            self._repository,
            roll_number=data.roll_number,
            university_enrollment=data.university_enrollment,
        )
        if duplicates:
            existing = duplicates[0]
            raise ObjectAlreadyExistsError(
                f"Duplicate student: {existing.id} ({existing.title!r}) already has this "
                f"roll number or enrollment id."
            )

        # 3. Linked Objects (supervisors, projects, …) must exist before edges
        for group, ids in (data.links or {}).items():
            kind = GROUP_TO_KIND[group]
            for target_id in ids:
                if target_id == ObjectId("") or not self._repository.exists(target_id):
                    raise ValidationError(f"Linked object {target_id} not found.")
                _ = kind  # kind is applied on write below

        # 4. Assemble the L6 human-asserted metadata record
        entries: list[MetadataEntry] = [
            MetadataEntry(
                KEY_STUDENT_TYPE, data.student_type,
                MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED,
            )
        ]

        def asserted(key: str, value: str) -> None:
            entries.append(
                MetadataEntry(key, value, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
            )

        for key, value in (
            (KEY_ROLL_NUMBER, (data.roll_number or "").strip()),
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
        ):
            if value is not None and str(value) != "":
                asserted(key, str(value))
        if data.semester is not None:
            asserted(KEY_SEMESTER, str(data.semester))
        if data.tags:
            asserted(KEY_TAGS, encode_json_list(data.tags))

        # 5. Create the domain aggregate (emits ObjectCreated)
        obj = UniversalObject.create(
            object_type=ObjectType.STUDENT,
            title=data.name.strip(),
            created_by=data.created_by.strip(),
            status=data.status,
            metadata=Metadata(entries=tuple(entries)),
        )

        # 6. Asserted relationship edges per link group (Blueprint §3.1)
        for group, ids in (data.links or {}).items():
            for target_id in ids:
                obj.add_relationship(
                    target_id,
                    GROUP_TO_KIND[group],
                    Provenance.ASSERTED,
                    actor=data.created_by,
                )

        # 7. Persist via the abstract repository interface
        self._repository.save(obj)

        # 8. Collect + project domain events
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        # 9. Output DTO (linked objects batch-resolved in one call)
        all_ids = [oid for ids in (data.links or {}).values() for oid in ids]
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(all_ids)}
        return StudentOutput.from_domain(obj, events, linked_by_id=linked_by_id)
