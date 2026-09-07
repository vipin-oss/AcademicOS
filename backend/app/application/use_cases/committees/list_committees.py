"""Use case: List Committees — PART 9 search + filters + pagination.

Mirrors ``ListProjectsUseCase``/``ListFacultyUseCase``: token-AND ``q`` over an
own-metadata haystack PLUS member names (the PI reverse-scan precedent),
committee_type / department / status / chairperson / meeting_year filters,
name-ordered pagination. Empty-key fields never match (None-tolerant).
"""
from __future__ import annotations

from app.application.dtos.committee import (
    LEADERSHIP_ROLES,
    CommitteeOutput,
    ListCommitteesResult,
)
from app.application.queries.list_committees import ListCommitteesQuery
from app.application.use_cases.committees.helpers import (
    KEY_MEETING_DATE,
    leadership_names_of_committee,
    meetings_of_committee,
    member_names_of_committee,
    resolve_members,
)
from app.application.validators.committee import assert_valid_list_committees_query
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind


def _haystack(obj: CommitteeOutput, member_names: str) -> str:
    meta = obj.metadata
    parts = [
        obj.name,
        meta.get("committee_code"),
        meta.get("committee_type"),
        meta.get("department"),
        meta.get("school"),
        meta.get("description"),
        meta.get("notes"),
        member_names,
    ]
    return " ".join(part for part in parts if part).casefold()


class ListCommitteesUseCase:
    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def execute(self, query: ListCommitteesQuery) -> ListCommitteesResult:
        assert_valid_list_committees_query(query)

        # M26 fast path: an unfiltered directory listing pages directly in SQL
        # (count + find, title-ordered — the registry's name order, since
        # CommitteeOutput.name is the object title) instead of loading every
        # COMMITTEE row and hydrating all JSONB metadata before slicing. The
        # slow path below is preserved for queries with criteria the SQL
        # projection cannot express (q tokens, type/department/chairperson/
        # meeting-year filters).
        plain = (
            not (query.q or "").strip()
            and query.committee_type is None
            and query.department is None
            and query.status is None
            and not (query.chairperson or "").strip()
            and query.meeting_year is None
        )
        if plain:
            total_count = self._repository.count(
                object_type=ObjectType.COMMITTEE, owner_user_id=query.owner_user_id
            )
            page = self._repository.find(
                object_type=ObjectType.COMMITTEE,
                owner_user_id=query.owner_user_id,
                page=query.page,
                page_size=query.page_size,
                sort_by="title_ci",
                order="asc",
            )
            items: list[CommitteeOutput] = []
            for obj in page:
                link_ids = [
                    rel.target
                    for rel in obj.relationships
                    if rel.kind is RelationshipKind.RELATED_TO
                ]
                linked_by_id = {
                    str(o.id): o for o in self._repository.find_by_ids(link_ids, owner_user_id=query.owner_user_id)
                }
                out = CommitteeOutput.from_domain(obj, [], linked_by_id=linked_by_id)
                out.members = resolve_members(self._repository, obj)
                items.append(out)
            return ListCommitteesResult(
                items=items,
                total_count=total_count,
                page=query.page,
                page_size=query.page_size,
            )

        objects = self._repository.find_by_type(
            ObjectType.COMMITTEE, owner_user_id=query.owner_user_id
        )

        tokens = (query.q or "").strip().casefold().split()
        chair_tokens = (query.chairperson or "").strip().casefold().split()
        wanted_type = (query.committee_type or "").strip().casefold()
        wanted_dept = (query.department or "").strip().casefold()
        # Perf hardening (Phase 2B audit follow-up): fetch every meeting
        # ONCE (only when the meeting_year filter is actually in use) and
        # share it across every candidate committee, instead of
        # meetings_of_committee() re-scanning the user's entire MEETING
        # table per committee — the N+1 the sweep found in this loop.
        all_meetings = (
            self._repository.find_by_type(ObjectType.MEETING, owner_user_id=query.owner_user_id)
            if query.meeting_year is not None
            else None
        )

        matched: list[CommitteeOutput] = []
        for obj in objects:
            meta = {entry.key: entry.value for entry in obj.metadata.entries}
            if wanted_type and (meta.get("committee_type") or "").strip().casefold() != wanted_type:
                continue
            if wanted_dept and wanted_dept not in (meta.get("department") or "").strip().casefold():
                continue
            if query.status and obj.status.value != query.status:
                continue
            link_ids = [
                rel.target for rel in obj.relationships
                if rel.kind is RelationshipKind.RELATED_TO
            ]
            linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(link_ids, owner_user_id=query.owner_user_id)}
            out = CommitteeOutput.from_domain(obj, [], linked_by_id=linked_by_id)
            # List rows carry resolved members too (leadership line in the UI).
            out.members = resolve_members(self._repository, obj)
            names = member_names_of_committee(self._repository, obj)
            if tokens:
                haystack = _haystack(out, names)
                if any(token not in haystack for token in tokens):
                    continue
            if chair_tokens:
                leaders = leadership_names_of_committee(
                    self._repository, obj, LEADERSHIP_ROLES
                ).casefold()
                if any(token not in leaders for token in chair_tokens):
                    continue
            if query.meeting_year is not None:
                prefix = f"{query.meeting_year:04d}-"
                if not any(
                    (
                        {e.key: e.value for e in meeting.metadata.entries}
                        .get(KEY_MEETING_DATE) or ""
                    ).startswith(prefix)
                    for meeting in meetings_of_committee(
                        self._repository, str(obj.id),
                        owner_user_id=query.owner_user_id, meetings=all_meetings,
                    )
                ):
                    continue
            matched.append(out)

        matched.sort(key=lambda item: (item.name.casefold(), item.id))
        total = len(matched)
        start = (query.page - 1) * query.page_size
        items = matched[start:start + query.page_size]
        return ListCommitteesResult(
            items=items, total_count=total, page=query.page, page_size=query.page_size
        )
