"""Use case: Update a Faculty member (partial — frozen merge contract).

Employee-id / faculty-code changes re-run duplicate detection (409); every
present field replaces verbatim (``None`` = untouched — the frozen
update_agency contract); profile sections replace per provided list (an
empty list clears the section); committee memberships replace only when the
group is present.
"""
from __future__ import annotations

import json

from app.application.commands.update_faculty import UpdateFacultyCommand
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
from app.application.exceptions import ObjectAlreadyExistsError, ObjectNotFoundError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.faculty.create_faculty import (
    assert_committee_targets,
    find_faculty_duplicates,
)
from app.application.validators.faculty import assert_valid_update_faculty_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import MetadataEntry
from app.domain.value_objects.object_id import ObjectId


class UpdateFacultyUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def _set(self, obj: UniversalObject, key: str, value: str, actor: str) -> None:
        if obj.metadata.get_value(key) != value:
            obj.set_metadata(
                MetadataEntry(key, value, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED),
                actor=actor,
            )

    def execute(self, command: UpdateFacultyCommand) -> FacultyOutput:
        data = command.input
        assert_valid_update_faculty_input(data)

        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.FACULTY:
            raise ObjectNotFoundError(f"Faculty {command.object_id} not found.")

        actor = data.actor.strip()

        if data.employee_id is not None or data.faculty_code is not None:
            meta = {entry.key: entry.value for entry in obj.metadata.entries}
            dupes = find_faculty_duplicates(
                self._repository,
                employee_id=(
                    data.employee_id if data.employee_id is not None else meta.get(KEY_EMPLOYEE_ID)
                ),
                faculty_code=(
                    data.faculty_code if data.faculty_code is not None else meta.get(KEY_FACULTY_CODE)
                ),
                exclude_id=str(obj.id),
            )
            if dupes:
                raise ObjectAlreadyExistsError(
                    f"Duplicate faculty: {dupes[0].id} ({dupes[0].title!r}) already carries "
                    f"this employee id / faculty code."
                )

        if data.name is not None and data.name.strip() != obj.title:
            obj.rename(data.name, actor)
        if data.status is not None and data.status != obj.status:
            obj.change_status(data.status, actor)

        for key, value in (
            (KEY_EMPLOYEE_ID, data.employee_id),
            (KEY_FACULTY_CODE, data.faculty_code),
            (KEY_DESIGNATION, data.designation),
            (KEY_DEPARTMENT, data.department),
            (KEY_SCHOOL, data.school),
            (KEY_JOINING_DATE, data.joining_date),
            (KEY_EMPLOYMENT_TYPE, data.employment_type),
            (KEY_EMAIL, data.email),
            (KEY_MOBILE, data.mobile),
            (KEY_OFFICE, data.office),
            (KEY_QUALIFICATION, data.qualification),
            (KEY_SPECIALIZATION, data.specialization),
            (KEY_BIOGRAPHY, data.biography),
            (KEY_ORCID, data.orcid),
            (KEY_SCOPUS_ID, data.scopus_id),
            (KEY_GOOGLE_SCHOLAR, data.google_scholar),
            (KEY_RESEARCHGATE, data.researchgate),
            (KEY_WEBSITE, data.website),
            (KEY_NOTES, data.notes),
        ):
            if value is not None:
                self._set(obj, key, str(value), actor)

        for key, value in (
            (KEY_RESEARCH_INTERESTS, data.research_interests),
            (KEY_TAGS, data.tags),
        ):
            if value is not None:
                self._set(obj, key, json.dumps(value, ensure_ascii=False), actor)

        for key, items in (
            (KEY_DEGREES, data.degrees),
            (KEY_EXPERIENCE, data.experience),
            (KEY_AWARDS, data.awards),
            (KEY_MEMBERSHIPS, data.memberships),
            (KEY_CERTIFICATIONS, data.certifications),
            (KEY_ADMIN_POSITIONS, data.admin_positions),
        ):
            if items is not None:
                self._set(obj, key, json.dumps(items, ensure_ascii=False), actor)

        if data.committees is not None:
            new_ids = {ObjectId.parse(raw) for raw in data.committees}
            assert_committee_targets(self._repository, sorted(new_ids, key=str))
            existing = {
                rel.target: rel
                for rel in obj.relationships
                if rel.kind is RelationshipKind.MEMBER_OF
            }
            for target in list(existing):
                if target not in new_ids:
                    obj.remove_relationship(
                        target, RelationshipKind.MEMBER_OF, Provenance.ASSERTED, actor=actor
                    )
            for target in new_ids:
                if target not in existing:
                    obj.add_relationship(target, RelationshipKind.MEMBER_OF,
                                         Provenance.ASSERTED, actor=actor)

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        committee_ids = [rel.target for rel in obj.relationships
                         if rel.kind is RelationshipKind.MEMBER_OF]
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(committee_ids)}
        return FacultyOutput.from_domain(obj, events, linked_by_id=linked_by_id)
