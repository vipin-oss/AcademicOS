"""Use case: Update a Vendor — the frozen merge contract.

Mirrors ``UpdateCommitteeUseCase``: None = untouched, a provided value
replaces verbatim; tags/bank_details are group-replaces; a name/GST change
re-runs the registry duplicate scan (409).
"""
from __future__ import annotations

import json

from app.application.commands.update_vendor import UpdateVendorCommand
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
from app.application.exceptions import ObjectAlreadyExistsError, ObjectNotFoundError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.finance.create_vendor import find_vendor_duplicates
from app.application.use_cases.finance.helpers import vendor_stats
from app.application.validators.finance import assert_valid_update_vendor_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import MetadataLayer, ObjectType, Provenance
from app.domain.value_objects.metadata import MetadataEntry


class UpdateVendorUseCase:
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

    def execute(self, command: UpdateVendorCommand) -> VendorOutput:
        data = command.input
        assert_valid_update_vendor_input(data)
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.VENDOR:
            raise ObjectNotFoundError(f"Vendor {command.object_id} not found.")

        actor = data.actor.strip()
        meta = {entry.key: entry.value for entry in obj.metadata.entries}

        if data.name is not None or data.gst_number is not None:
            duplicates = find_vendor_duplicates(
                self._repository,
                name=data.name if data.name is not None else obj.title,
                gst_number=(
                    data.gst_number if data.gst_number is not None else meta.get(KEY_GST_NUMBER)
                ),
                exclude_id=str(obj.id),
            )
            if duplicates:
                raise ObjectAlreadyExistsError(
                    f"Duplicate vendor: {duplicates[0].id} ({duplicates[0].title!r}) already "
                    f"carries this name / GST number."
                )

        if data.name is not None and data.name.strip() != obj.title:
            obj.rename(data.name, actor)
        if data.status is not None and data.status != obj.status:
            obj.change_status(data.status, actor)

        for key, value in (
            (KEY_GST_NUMBER, (data.gst_number or "").strip().upper() if data.gst_number is not None else None),
            (KEY_PAN, (data.pan or "").strip().upper() if data.pan is not None else None),
            (KEY_CONTACT_PERSON, data.contact_person),
            (KEY_EMAIL, data.email),
            (KEY_PHONE, data.phone),
            (KEY_ADDRESS, data.address),
            (KEY_NOTES, data.notes),
        ):
            if value is not None:
                self._set(obj, key, str(value), actor)

        if data.bank_details is not None:
            self._set(obj, KEY_BANK_DETAILS, json.dumps(data.bank_details, ensure_ascii=False), actor)
        if data.tags is not None:
            self._set(obj, KEY_TAGS, json.dumps(data.tags, ensure_ascii=False), actor)

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)
        output = VendorOutput.from_domain(obj, events)
        output.stats = vendor_stats(self._repository, str(obj.id))
        return output
