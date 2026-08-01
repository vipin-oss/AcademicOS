"""Use case: Update a Publication (partial; metadata + link groups — no PDF).

Mirrors ``UpdateDocumentUseCase``: every mutation goes through its dedicated
aggregate method (``rename`` / ``change_status`` / ``set_metadata`` /
``add/remove_relationship``) so versioning, audit and domain events stay
intact. Link groups use merge semantics: a group present in ``links`` replaces
its edges with exactly the given ids; absent groups are untouched. Duplicate
detection re-runs when DOI or title changes (excluding the Object itself).
"""
from __future__ import annotations

from app.application.commands.update_publication import UpdatePublicationCommand
from app.application.dtos.publication import (
    _TYPE_TO_GROUP,
    GROUP_TO_KIND,
    KEY_ABSTRACT,
    KEY_AFFILIATIONS,
    KEY_AUTHORS,
    KEY_CITATION_COUNT,
    KEY_COLLECTIONS,
    KEY_CONFERENCE,
    KEY_DATE,
    KEY_DOI,
    KEY_IMPACT_FACTOR,
    KEY_INDEXING,
    KEY_ISBN,
    KEY_ISSN,
    KEY_ISSUE,
    KEY_JOURNAL,
    KEY_KEYWORDS,
    KEY_LANGUAGE,
    KEY_NOTES,
    KEY_PAGES,
    KEY_PIPELINE_STAGE,
    KEY_PUBLICATION_TYPE,
    KEY_PUBLISHER,
    KEY_PUBLISHER_URL,
    KEY_QUARTILE,
    KEY_TAGS,
    KEY_VOLUME,
    KEY_YEAR,
    PublicationOutput,
    encode_json_list,
    linked_target_ids,
)
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ValidationError,
)
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.publications.create_publication import (
    find_duplicates,
)
from app.application.validators.publication import (
    assert_valid_update_publication_input,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import MetadataEntry


class UpdatePublicationUseCase:
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

    def execute(self, command: UpdatePublicationCommand) -> PublicationOutput:
        data = command.input
        assert_valid_update_publication_input(data)

        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.PUBLICATION:
            raise ObjectNotFoundError(f"Publication {command.object_id} not found.")

        actor = data.actor.strip()

        # --- duplicate detection when DOI/title changes -----------------
        new_doi = data.doi if data.doi is not None else obj.metadata.get_value(KEY_DOI)
        new_title = data.title.strip() if data.title is not None else obj.title
        if (data.doi is not None and data.doi != obj.metadata.get_value(KEY_DOI)) or (
            data.title is not None and new_title != obj.title
        ):
            dupes = [
                dup
                for dup in find_duplicates(self._repository, doi=new_doi, title=new_title)
                if dup.id != obj.id
            ]
            if dupes:
                raise ObjectAlreadyExistsError(
                    f"Possible duplicate: publication {dupes[0].id} "
                    f"({dupes[0].title!r}) already exists."
                )

        # --- link groups (validate first, then merge per group) ---------
        if data.links is not None:
            for group, ids in data.links.items():
                kind = GROUP_TO_KIND[group]
                wanted = {str(oid) for oid in ids}
                for oid in ids:
                    if oid == obj.id:
                        raise ValidationError("A publication cannot be linked to itself.")
                    if not self._repository.exists(oid):
                        raise ValidationError(f"Linked object {oid} not found.")
                current = [r.target for r in obj.relationships if r.kind == kind]
                for target in current:
                    if str(target) not in wanted and self._group_of(target) == group:
                        obj.remove_relationship(target, kind, Provenance.ASSERTED, actor=actor)
                present = {str(r.target) for r in obj.relationships if r.kind == kind}
                for oid in ids:
                    if str(oid) not in present:
                        obj.add_relationship(oid, kind, Provenance.ASSERTED, actor=actor)

        # --- title / lifecycle ------------------------------------------
        if data.title is not None and data.title.strip() != obj.title:
            obj.rename(data.title, actor)
        if data.status is not None and data.status != obj.status:
            obj.change_status(data.status, actor)

        # --- human-asserted metadata (L6) --------------------------------
        scalar_fields = (
            (KEY_PUBLICATION_TYPE, data.publication_type),
            (KEY_PIPELINE_STAGE, data.pipeline_stage),
            (KEY_ABSTRACT, data.abstract),
            (KEY_DOI, data.doi),
            (KEY_ISBN, data.isbn),
            (KEY_ISSN, data.issn),
            (KEY_PUBLISHER, data.publisher),
            (KEY_JOURNAL, data.journal),
            (KEY_CONFERENCE, data.conference),
            (KEY_VOLUME, data.volume),
            (KEY_ISSUE, data.issue),
            (KEY_PAGES, data.pages),
            (KEY_DATE, data.date),
            (KEY_LANGUAGE, data.language),
            (KEY_QUARTILE, data.quartile),
            (KEY_PUBLISHER_URL, data.publisher_url),
            (KEY_NOTES, data.notes),
        )
        for key, value in scalar_fields:
            if value is not None:
                self._assert(obj, key, str(value), actor)
        if data.year is not None:
            self._assert(obj, KEY_YEAR, str(data.year), actor)
        if data.citation_count is not None:
            self._assert(obj, KEY_CITATION_COUNT, str(data.citation_count), actor)
        if data.impact_factor is not None:
            self._assert(obj, KEY_IMPACT_FACTOR, str(data.impact_factor), actor)
        for key, values in (
            (KEY_AUTHORS, data.authors),
            (KEY_AFFILIATIONS, data.affiliations),
            (KEY_KEYWORDS, data.keywords),
            (KEY_INDEXING, data.indexing),
            (KEY_TAGS, data.tags),
            (KEY_COLLECTIONS, data.collections),
        ):
            if values is not None:
                self._assert(obj, key, encode_json_list(values), actor)

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        linked_by_id = {
            str(o.id): o for o in self._repository.find_by_ids(linked_target_ids(obj))
        }
        return PublicationOutput.from_domain(obj, events, linked_by_id=linked_by_id)

    def _group_of(self, target) -> str | None:
        linked = self._repository.get_by_id(target)
        if linked is None:
            return None
        return _TYPE_TO_GROUP.get(linked.object_type)
