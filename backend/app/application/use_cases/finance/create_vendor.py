"""Use case: Register a Vendor (PART 3 registry).

Mirrors ``CreateCommitteeUseCase``: validate -> duplicate scan (GST number,
else vendor name; 409) -> L6 metadata record -> persist -> events -> output.
"""
from __future__ import annotations

import json

from app.application.commands.create_vendor import CreateVendorCommand
from app.application.dtos.finance import (
    KEY_ADDRESS,
    KEY_BANK_DETAILS,
    KEY_CONTACT_PERSON,
    KEY_EMAIL,
    KEY_GST_NUMBER,
    KEY_NOTES,
    KEY_PAN,
    KEY_PHONE,
    KEY_TAGS,
    VendorOutput,
)
from app.application.exceptions import ObjectAlreadyExistsError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.validators.finance import assert_valid_create_vendor_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import Metadata, MetadataEntry


def find_vendor_duplicates(
    repository: ObjectRepository,
    *,
    name: str | None,
    gst_number: str | None,
    exclude_id: str | None = None,
) -> list[UniversalObject]:
    """Registry duplicate detection: GST number, else the exact name."""
    wanted_gst = (gst_number or "").strip().casefold()
    wanted_name = (name or "").strip().casefold()
    if not (wanted_gst or wanted_name):
        return []
    matches: list[UniversalObject] = []
    for obj in repository.find_by_type(ObjectType.VENDOR):
        if exclude_id is not None and str(obj.id) == exclude_id:
            continue
        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        if wanted_gst and (meta.get(KEY_GST_NUMBER) or "").strip().casefold() == wanted_gst:
            matches.append(obj)
            continue
        if wanted_name and obj.title.strip().casefold() == wanted_name:
            matches.append(obj)
    return matches


class CreateVendorUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: CreateVendorCommand) -> VendorOutput:
        data = command.input
        assert_valid_create_vendor_input(data)

        duplicates = find_vendor_duplicates(
            self._repository, name=data.name, gst_number=data.gst_number
        )
        if duplicates:
            existing = duplicates[0]
            raise ObjectAlreadyExistsError(
                f"Duplicate vendor: {existing.id} ({existing.title!r}) already carries this "
                f"name / GST number."
            )

        entries: list[MetadataEntry] = []

        def put(key: str, value: object) -> None:
            if value is None or str(value) == "":
                return
            entries.append(
                MetadataEntry(key, str(value), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
            )

        put(KEY_GST_NUMBER, (data.gst_number or "").strip().upper() or None)
        put(KEY_PAN, (data.pan or "").strip().upper() or None)
        put(KEY_CONTACT_PERSON, data.contact_person)
        put(KEY_EMAIL, data.email)
        put(KEY_PHONE, data.phone)
        put(KEY_ADDRESS, data.address)
        if data.bank_details:
            put(KEY_BANK_DETAILS, json.dumps(data.bank_details, ensure_ascii=False))
        put(KEY_NOTES, data.notes)
        put(KEY_TAGS, json.dumps(data.tags, ensure_ascii=False) if data.tags else None)

        obj = UniversalObject.create(
            object_type=ObjectType.VENDOR,
            title=data.name.strip(),
            created_by=data.created_by.strip(),
            status=data.status,
            metadata=Metadata(entries=tuple(entries)),
        )
        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        return VendorOutput.from_domain(obj, events)
