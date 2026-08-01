"""Use case: Update a Document (partial; metadata/link/status/title — no re-upload).

Applies only the mutations the frozen Domain aggregate supports, each through
its dedicated aggregate method so versioning, audit and domain events stay
intact:

  - title        -> ``obj.rename``            (human-asserted display title)
  - status       -> ``obj.change_status``     (lifecycle rules enforced)
  - type/descr./tags -> ``obj.set_metadata``  (L6 human-asserted entries)
  - object_id    -> ``add/remove_relationship`` (asserted ``belongs_to`` edge;
                    explicit ``null`` unlinks, absent field leaves as-is)

The aggregate is re-persisted through the existing ``save`` (upsert) — no new
repository method is introduced.
"""
from __future__ import annotations

from app.application.commands.update_document import UpdateDocumentCommand
from app.application.dtos.document import (
    KEY_DESCRIPTION,
    KEY_DOCUMENT_TYPE,
    KEY_TAGS,
    DocumentOutput,
    encode_tags,
    linked_object_id,
)
from app.application.exceptions import ObjectNotFoundError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.validators.document import assert_valid_update_document_input
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import MetadataEntry


class UpdateDocumentUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: UpdateDocumentCommand) -> DocumentOutput:
        data = command.input
        assert_valid_update_document_input(data)

        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.DOCUMENT:
            raise ObjectNotFoundError(f"Document {command.object_id} not found.")

        actor = data.actor.strip()

        # --- link/unlink (validate the target before mutating anything) ---
        if data.object_id_provided:
            current = linked_object_id(obj)
            same = data.object_id is not None and current == data.object_id
            if data.object_id == command.object_id:
                raise ValidationError("A document cannot be linked to itself.")
            if data.object_id is not None and not same:
                if not self._repository.exists(data.object_id):
                    raise ValidationError(f"Linked object {data.object_id} not found.")
            if not same:
                if current is not None:
                    obj.remove_relationship(
                        current, RelationshipKind.BELONGS_TO, Provenance.ASSERTED, actor=actor
                    )
                if data.object_id is not None:
                    obj.add_relationship(
                        data.object_id,
                        RelationshipKind.BELONGS_TO,
                        Provenance.ASSERTED,
                        actor=actor,
                    )

        # --- title ---
        if data.title is not None and data.title.strip() != obj.title:
            obj.rename(data.title, actor)

        # --- lifecycle ---
        if data.status is not None and data.status != obj.status:
            obj.change_status(data.status, actor)

        # --- human-asserted metadata (L6) ---
        if data.document_type is not None and data.document_type != obj.metadata.get_value(
            KEY_DOCUMENT_TYPE
        ):
            obj.set_metadata(
                MetadataEntry(
                    KEY_DOCUMENT_TYPE,
                    data.document_type,
                    MetadataLayer.L6_HUMAN_ASSERTED,
                    Provenance.ASSERTED,
                ),
                actor=actor,
            )
        if data.description is not None and data.description != obj.metadata.get_value(
            KEY_DESCRIPTION
        ):
            obj.set_metadata(
                MetadataEntry(
                    KEY_DESCRIPTION,
                    data.description,
                    MetadataLayer.L6_HUMAN_ASSERTED,
                    Provenance.ASSERTED,
                ),
                actor=actor,
            )
        if data.tags is not None:
            encoded = encode_tags(data.tags)
            if encoded != obj.metadata.get_value(KEY_TAGS):
                obj.set_metadata(
                    MetadataEntry(
                        KEY_TAGS,
                        encoded,
                        MetadataLayer.L6_HUMAN_ASSERTED,
                        Provenance.ASSERTED,
                    ),
                    actor=actor,
                )

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        link_id = linked_object_id(obj)
        linked = self._repository.get_by_id(link_id) if link_id is not None else None
        return DocumentOutput.from_domain(obj, events, linked=linked)
