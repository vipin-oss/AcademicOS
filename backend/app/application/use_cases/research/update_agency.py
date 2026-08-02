"""Use case: Update a Funding Agency (partial — frozen merge contract).

Name change re-runs duplicate detection (409); every present field replaces.
"""
from __future__ import annotations

from app.application.commands.update_agency import UpdateAgencyCommand
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
from app.application.exceptions import ObjectAlreadyExistsError, ObjectNotFoundError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.research.create_agency import find_agency_duplicates
from app.application.validators.research import assert_valid_update_agency_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import MetadataEntry


class UpdateAgencyUseCase:
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

    def execute(self, command: UpdateAgencyCommand) -> AgencyOutput:
        data = command.input
        assert_valid_update_agency_input(data)

        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.FUNDING_AGENCY:
            raise ObjectNotFoundError(f"Funding agency {command.object_id} not found.")

        actor = data.actor.strip()

        if data.name is not None and data.name.strip().casefold() != obj.title.strip().casefold():
            dupes = find_agency_duplicates(
                self._repository, name=data.name, exclude_id=str(obj.id)
            )
            if dupes:
                raise ObjectAlreadyExistsError(
                    f"Duplicate funding agency: {dupes[0].id} ({dupes[0].title!r}) already "
                    f"exists."
                )

        if data.name is not None and data.name.strip() != obj.title:
            obj.rename(data.name, actor)
        if data.status is not None and data.status != obj.status:
            obj.change_status(data.status, actor)

        for key, value in (
            (KEY_AGENCY_WEBSITE, data.website),
            (KEY_AGENCY_SCHEME, data.scheme),
            (KEY_AGENCY_CONTACT_PERSON, data.contact_person),
            (KEY_AGENCY_EMAIL, data.contact_email),
            (KEY_AGENCY_PHONE, data.contact_phone),
            (KEY_AGENCY_ADDRESS, data.address),
            (KEY_NOTES, data.notes),
        ):
            if value is not None:
                self._assert(obj, key, str(value), actor)

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return AgencyOutput.from_domain(obj, events)
