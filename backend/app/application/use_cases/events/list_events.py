"""Use case: List Events — PART 10 search + filters + pagination.

Mirrors ``ListProposalsUseCase``: token-AND ``q`` over an own-metadata
haystack PLUS speaker names (the finance vendor-name haystack precedent);
event_type / year (calendar year of start_date) / participation role /
department / organizer / status filters; title-ordered pagination. List rows
go through the ONE shared enrichment (``enrich_event_output``) — resolved
speaker/document/publication refs, normalised link groups and the computed
stats block — so a directory row carries exactly the workspace payload's
denormalised shape.
"""
from __future__ import annotations

from app.application.dtos.events import (
    KEY_CO_ORGANIZER,
    KEY_DEPARTMENT,
    KEY_DESCRIPTION,
    KEY_EVENT_CODE,
    KEY_EVENT_STATUS,
    KEY_EVENT_TYPE,
    KEY_NOTES,
    KEY_ORGANIZER,
    KEY_PARTICIPATION,
    KEY_SCHOOL,
    KEY_SPEAKERS,
    KEY_START_DATE,
    KEY_VENUE,
    EventOutput,
    ListEventsResult,
)
from app.application.queries.list_events import ListEventsQuery
from app.application.use_cases.events.helpers import (
    enrich_event_output,
    section_rows,
)
from app.application.validators.events import (
    assert_optional_year,
    assert_valid_list_query,
)
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind


def _meta(obj) -> dict[str, str]:
    return {entry.key: entry.value for entry in obj.metadata.entries}


class ListEventsUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListEventsQuery) -> ListEventsResult:
        assert_valid_list_query(query.page, query.page_size)
        assert_optional_year(query.year)

        # M26 fast path: an unfiltered directory listing pages directly in SQL
        # (count + find, title-ordered — the registry's title order) instead
        # of loading every EVENT row and hydrating all JSONB metadata before
        # slicing. The slow path below is preserved for queries with criteria
        # the SQL projection cannot express (q tokens, type/year/role/
        # department/organizer/status filters).
        plain = (
            not (query.q or "").strip()
            and not (query.event_type or "").strip()
            and not (query.year or "").strip()
            and not (query.role or "").strip()
            and not (query.department or "").strip()
            and not (query.organizer or "").strip()
            and not (query.status or "").strip()
        )
        if plain:
            total_count = self._repository.count(object_type=ObjectType.EVENT)
            page = self._repository.find(
                object_type=ObjectType.EVENT,
                page=query.page,
                page_size=query.page_size,
                sort_by="title_ci",
                order="asc",
            )
            items: list[EventOutput] = []
            for obj in page:
                link_ids = [
                    rel.target
                    for rel in obj.relationships
                    if rel.kind is RelationshipKind.RELATED_TO
                ]
                linked_by_id = {
                    str(o.id): o for o in self._repository.find_by_ids(link_ids)
                }
                out = EventOutput.from_domain(obj, [], linked_by_id=linked_by_id)
                enrich_event_output(self._repository, obj, out)
                items.append(out)
            return ListEventsResult(
                items=items,
                total_count=total_count,
                page=query.page,
                page_size=query.page_size,
            )

        objects = self._repository.find_by_type(ObjectType.EVENT)

        tokens = (query.q or "").strip().casefold().split()
        wanted_type = (query.event_type or "").strip()
        wanted_year = (query.year or "").strip()
        wanted_role = (query.role or "").strip()
        wanted_dept = (query.department or "").strip().casefold()
        organizer_tokens = (query.organizer or "").strip().casefold().split()
        wanted_status = (query.status or "").strip()

        matched: list[EventOutput] = []
        for obj in objects:
            meta = _meta(obj)
            if wanted_type and (meta.get(KEY_EVENT_TYPE) or "") != wanted_type:
                continue
            if wanted_status and (meta.get(KEY_EVENT_STATUS) or "planned") != wanted_status:
                continue
            if wanted_dept and wanted_dept not in (
                meta.get(KEY_DEPARTMENT) or ""
            ).strip().casefold():
                continue
            if wanted_year:
                start = (meta.get(KEY_START_DATE) or "").strip()
                if start[:4] != wanted_year:
                    continue
            participation = section_rows(meta, KEY_PARTICIPATION)
            if wanted_role and not any(
                (row.get("role") or "") == wanted_role for row in participation
            ):
                continue

            organizer_text = " ".join(
                part
                for part in (meta.get(KEY_ORGANIZER), meta.get(KEY_CO_ORGANIZER))
                if part
            ).casefold()
            if organizer_tokens and any(
                token not in organizer_text for token in organizer_tokens
            ):
                continue

            if tokens:
                speaker_names = " ".join(
                    str(row.get("name") or "")
                    for row in section_rows(meta, KEY_SPEAKERS)
                )
                haystack = " ".join(
                    part
                    for part in (
                        obj.title,
                        meta.get(KEY_EVENT_CODE),
                        meta.get(KEY_ORGANIZER),
                        meta.get(KEY_CO_ORGANIZER),
                        meta.get(KEY_VENUE),
                        meta.get(KEY_DEPARTMENT),
                        meta.get(KEY_SCHOOL),
                        meta.get(KEY_DESCRIPTION),
                        meta.get(KEY_NOTES),
                        speaker_names,
                    )
                    if part
                ).casefold()
                if any(token not in haystack for token in tokens):
                    continue

            link_ids = [
                rel.target for rel in obj.relationships
                if rel.kind is RelationshipKind.RELATED_TO
            ]
            linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(link_ids)}
            out = EventOutput.from_domain(obj, [], linked_by_id=linked_by_id)
            enrich_event_output(self._repository, obj, out)
            matched.append(out)

        matched.sort(key=lambda item: (item.title.casefold(), item.id))
        total = len(matched)
        start = (query.page - 1) * query.page_size
        items = matched[start:start + query.page_size]
        return ListEventsResult(
            items=items, total_count=total, page=query.page, page_size=query.page_size
        )
