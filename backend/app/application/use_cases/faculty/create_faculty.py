"""Use case: Register a Faculty member (PART 1 directory + PART 2 profile).

Mirrors ``CreateStudentUseCase``/``RegisterAgencyUseCase``: validate ->
duplicate check (employee id / faculty code, registry identity, 409) ->
committee target assertions (422) -> L6 metadata record -> MEMBER_OF edges
(on the faculty aggregate) -> persist -> events -> output.
"""
from __future__ import annotations

import json

from app.application.commands.create_faculty import CreateFacultyCommand
from app.application.dtos.faculty import (
    KEY_ADMIN_POSITIONS,
    KEY_AWARDS,
    KEY_BIOGRAPHY,
    KEY_CERTIFICATIONS,
    KEY_DEGREES,
    KEY_DEPARTMENT,
    KEY_DESIGNATION,
    KEY_EMAIL,
    KEY_EMPLOYEE_ID,
    KEY_EMPLOYMENT_TYPE,
    KEY_EXPERIENCE,
    KEY_FACULTY_CODE,
    KEY_GOOGLE_SCHOLAR,
    KEY_JOINING_DATE,
    KEY_MEMBERSHIPS,
    KEY_MOBILE,
    KEY_NOTES,
    KEY_OFFICE,
    KEY_ORCID,
    KEY_QUALIFICATION,
    KEY_RESEARCH_INTERESTS,
    KEY_RESEARCHGATE,
    KEY_SCHOOL,
    KEY_SCOPUS_ID,
    KEY_SPECIALIZATION,
    KEY_TAGS,
    KEY_WEBSITE,
    FacultyOutput,
)
from app.application.exceptions import ObjectAlreadyExistsError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.validators.faculty import assert_valid_create_faculty_input
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


def find_faculty_duplicates(
    repository: ObjectRepository,
    *,
    employee_id: str | None,
    faculty_code: str | None,
    exclude_id: str | None = None,
) -> list[UniversalObject]:
    """Registry duplicate detection: employee id / faculty code (case-insensitive)."""
    wanted_employee = (employee_id or "").strip().casefold()
    wanted_code = (faculty_code or "").strip().casefold()
    if not wanted_employee and not wanted_code:
        return []
    matches: list[UniversalObject] = []
    for obj in repository.find_by_type(ObjectType.FACULTY):
        if exclude_id is not None and str(obj.id) == exclude_id:
            continue
        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        if wanted_employee and (meta.get(KEY_EMPLOYEE_ID) or "").strip().casefold() == wanted_employee:
            matches.append(obj)
            continue
        if wanted_code and (meta.get(KEY_FACULTY_CODE) or "").strip().casefold() == wanted_code:
            matches.append(obj)
    return matches


def assert_committee_targets(repository: ObjectRepository, ids: list[ObjectId]) -> None:
    """Committee targets must exist and carry the COMMITTEE type (422)."""
    for target_id in ids:
        target = repository.get_by_id(target_id)
        if target is None:
            raise ValidationError(f"Linked committee {target_id} not found.")
        if target.object_type is not ObjectType.COMMITTEE:
            raise ValidationError(
                f"committees expects committee targets; {target_id} is a "
                f"{target.object_type.value}."
            )


class CreateFacultyUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: CreateFacultyCommand) -> FacultyOutput:
        data = command.input
        assert_valid_create_faculty_input(data)

        duplicates = find_faculty_duplicates(
            self._repository, employee_id=data.employee_id, faculty_code=data.faculty_code
        )
        if duplicates:
            existing = duplicates[0]
            raise ObjectAlreadyExistsError(
                f"Duplicate faculty: {existing.id} ({existing.title!r}) already carries this "
                f"employee id / faculty code."
            )

        committee_ids = [ObjectId.parse(raw) for raw in data.committees]
        assert_committee_targets(self._repository, committee_ids)

        entries: list[MetadataEntry] = []

        def put(key: str, value: object) -> None:
            if value is None or str(value) == "":
                return
            entries.append(
                MetadataEntry(
                    key, str(value), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED
                )
            )

        put(KEY_EMPLOYEE_ID, data.employee_id.strip())
        put(KEY_FACULTY_CODE, data.faculty_code)
        put(KEY_DESIGNATION, data.designation)
        put(KEY_DEPARTMENT, data.department)
        put(KEY_SCHOOL, data.school)
        put(KEY_JOINING_DATE, data.joining_date)
        put(KEY_EMPLOYMENT_TYPE, data.employment_type)
        put(KEY_EMAIL, data.email)
        put(KEY_MOBILE, data.mobile)
        put(KEY_OFFICE, data.office)
        put(KEY_QUALIFICATION, data.qualification)
        put(KEY_SPECIALIZATION, data.specialization)
        put(KEY_RESEARCH_INTERESTS, json.dumps(data.research_interests, ensure_ascii=False))
        put(KEY_BIOGRAPHY, data.biography)
        put(KEY_ORCID, data.orcid)
        put(KEY_SCOPUS_ID, data.scopus_id)
        put(KEY_GOOGLE_SCHOLAR, data.google_scholar)
        put(KEY_RESEARCHGATE, data.researchgate)
        put(KEY_WEBSITE, data.website)
        put(KEY_NOTES, data.notes)
        put(KEY_TAGS, json.dumps(data.tags, ensure_ascii=False))
        for key, items in (
            (KEY_DEGREES, data.degrees),
            (KEY_EXPERIENCE, data.experience),
            (KEY_AWARDS, data.awards),
            (KEY_MEMBERSHIPS, data.memberships),
            (KEY_CERTIFICATIONS, data.certifications),
            (KEY_ADMIN_POSITIONS, data.admin_positions),
        ):
            if items:
                put(key, json.dumps(items, ensure_ascii=False))

        obj = UniversalObject.create(
            object_type=ObjectType.FACULTY,
            title=data.name.strip(),
            created_by=data.created_by.strip(),
            status=data.status,
            metadata=Metadata(entries=tuple(entries)),
        )
        for target_id in committee_ids:
            obj.add_relationship(
                target_id, RelationshipKind.MEMBER_OF, Provenance.ASSERTED,
                actor=data.created_by.strip(),
            )

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(committee_ids)}
        return FacultyOutput.from_domain(obj, events, linked_by_id=linked_by_id)
