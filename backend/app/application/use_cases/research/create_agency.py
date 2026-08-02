"""Use case: Register a Funding Agency (DST, CSIR, UGC, ICSSR, DBT, ICMR,
AICTE, SERB, Haryana HSRF, …).

Mirrors ``CreateStudentUseCase``: validate -> duplicate check (agency name,
registry identity, 409) -> L6 metadata record -> persist -> events -> output.
"""
from __future__ import annotations

from app.application.commands.create_agency import CreateAgencyCommand
from app.application.dtos.research import (
    KEY_AGENCY_ADDRESS,
    KEY_AGENCY_CONTACT_PERSON,
    KEY_AGENCY_EMAIL,
    KEY_AGENCY_PHONE,
    KEY_AGENCY_SCHEME,
    KEY_AGENCY_WEBSITE,
    KEY_NOTES,
    AgencyOutput,
)
from app.application.exceptions import ObjectAlreadyExistsError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.validators.research import assert_valid_create_agency_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import Metadata, MetadataEntry


def find_agency_duplicates(
    repository: ObjectRepository,
    *,
    name: str | None,
    exclude_id: str | None = None,
) -> list[UniversalObject]:
    """Registry duplicate detection: agency name (case-insensitive, portable)."""
    wanted = (name or "").strip().casefold()
    if not wanted:
        return []
    matches: list[UniversalObject] = []
    for agency in repository.find_by_type(ObjectType.FUNDING_AGENCY):
        if exclude_id is not None and str(agency.id) == exclude_id:
            continue
        if agency.title.strip().casefold() == wanted:
            matches.append(agency)
    return matches


class CreateAgencyUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: CreateAgencyCommand) -> AgencyOutput:
        data = command.input
        assert_valid_create_agency_input(data)

        duplicates = find_agency_duplicates(self._repository, name=data.name)
        if duplicates:
            existing = duplicates[0]
            raise ObjectAlreadyExistsError(
                f"Duplicate funding agency: {existing.id} ({existing.title!r}) already exists."
            )

        entries: list[MetadataEntry] = []
        for key, value in (
            (KEY_AGENCY_WEBSITE, data.website),
            (KEY_AGENCY_SCHEME, data.scheme),
            (KEY_AGENCY_CONTACT_PERSON, data.contact_person),
            (KEY_AGENCY_EMAIL, data.contact_email),
            (KEY_AGENCY_PHONE, data.contact_phone),
            (KEY_AGENCY_ADDRESS, data.address),
            (KEY_NOTES, data.notes),
        ):
            if value is not None and str(value) != "":
                entries.append(
                    MetadataEntry(key, str(value),
                                  MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
                )

        obj = UniversalObject.create(
            object_type=ObjectType.FUNDING_AGENCY,
            title=data.name.strip(),
            created_by=data.created_by.strip(),
            status=data.status,
            metadata=Metadata(entries=tuple(entries)),
        )
        self._repository.save(obj)

        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return AgencyOutput.from_domain(obj, events)
