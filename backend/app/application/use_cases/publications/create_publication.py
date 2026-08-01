"""Use case: Register a Publication (manual entry / reference-manager create).

Mirrors ``CreateDocumentUseCase``: validate -> duplicate check -> build the
seven-layer metadata record (all bibliographic fields are L6 human-asserted)
-> asserted relationship edges per link group -> persist -> events -> output.

A Publication carries no file on creation — the primary PDF is attached later
through ``AttachPublicationPdfUseCase`` (mirrors Zotero's attach workflow);
supplementary files are linked Document objects (existing module).
"""
from __future__ import annotations

from app.application.commands.create_publication import CreatePublicationCommand
from app.application.dtos.publication import (
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
)
from app.application.exceptions import ObjectAlreadyExistsError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.services.bibliography import normalize_title
from app.application.validators.publication import (
    assert_valid_create_publication_input,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId


def find_duplicates(
    repository: ObjectRepository,
    *,
    doi: str | None,
    title: str,
) -> list[UniversalObject]:
    """Reference-manager duplicate detection: DOI (case-insensitive) or title.

    Both signals are evaluated in Python over ``find_by_type`` (the same
    frozen-interface call the list endpoint already uses), so detection is
    identical on PostgreSQL, SQLite, and in-memory repositories — it never
    depends on engine-specific JSONB containment operators.
    """
    candidates = repository.find_by_type(ObjectType.PUBLICATION)
    matches: list[UniversalObject] = []
    if doi and doi.strip():
        folded_doi = doi.strip().casefold()
        matches.extend(
            pub
            for pub in candidates
            if (pub.metadata.get_value(KEY_DOI) or "").strip().casefold() == folded_doi
        )
    if title.strip():
        folded_title = normalize_title(title)
        matches.extend(
            pub
            for pub in candidates
            if normalize_title(pub.title) == folded_title and pub not in matches
        )
    return matches


class CreatePublicationUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: CreatePublicationCommand) -> PublicationOutput:
        data = command.input

        # 1. Validate boundary input
        assert_valid_create_publication_input(data)

        # 2. Duplicate detection (DOI first, then normalised title) -> 409
        duplicates = find_duplicates(self._repository, doi=data.doi, title=data.title)
        if duplicates:
            existing = duplicates[0]
            raise ObjectAlreadyExistsError(
                f"Possible duplicate: publication {existing.id} "
                f"({existing.title!r}) already exists."
            )

        # 3. Linked Objects must exist before any edge is written
        for group, ids in (data.links or {}).items():
            kind = GROUP_TO_KIND[group]
            for target_id in ids:
                if target_id == ObjectId("") or not self._repository.exists(target_id):
                    raise ValidationError(f"Linked object {target_id} not found.")
                _ = kind  # kind is applied on write below

        # 4. Assemble the L6 human-asserted metadata record
        entries: list[MetadataEntry] = [
            MetadataEntry(
                KEY_PUBLICATION_TYPE, data.publication_type,
                MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED,
            )
        ]

        def asserted(key: str, value: str) -> None:
            entries.append(
                MetadataEntry(key, value, MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
            )

        if data.pipeline_stage:
            asserted(KEY_PIPELINE_STAGE, data.pipeline_stage)
        if data.authors:
            asserted(KEY_AUTHORS, encode_json_list(data.authors))
        if data.affiliations:
            asserted(KEY_AFFILIATIONS, encode_json_list(data.affiliations))
        for key, value in (
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
        ):
            if value is not None and str(value) != "":
                asserted(key, str(value))
        if data.keywords:
            asserted(KEY_KEYWORDS, encode_json_list(data.keywords))
        if data.year is not None:
            asserted(KEY_YEAR, str(data.year))
        if data.citation_count is not None:
            asserted(KEY_CITATION_COUNT, str(data.citation_count))
        if data.impact_factor is not None:
            asserted(KEY_IMPACT_FACTOR, str(data.impact_factor))
        if data.indexing:
            asserted(KEY_INDEXING, encode_json_list(data.indexing))
        if data.tags:
            asserted(KEY_TAGS, encode_json_list(data.tags))
        if data.collections:
            asserted(KEY_COLLECTIONS, encode_json_list(data.collections))

        # 5. Create the domain aggregate (emits ObjectCreated)
        obj = UniversalObject.create(
            object_type=ObjectType.PUBLICATION,
            title=data.title.strip(),
            created_by=data.uploaded_by.strip(),
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
                    actor=data.uploaded_by,
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
        return PublicationOutput.from_domain(obj, events, linked_by_id=linked_by_id)
