"""Use case: Update a Purchase Proposal — the frozen merge contract.

Mirrors ``UpdateCommitteeUseCase`` one-to-one: None = untouched, a provided
value replaces verbatim; tags/sections/link groups are group-replaces; a
number/title/department/date change re-runs the registry duplicate scan
(409); replaced sections re-run vendor/document assertions (422); a
requested_by change re-resolves the faculty display-name snapshot.
"""
from __future__ import annotations

import json

from app.application.commands.update_proposal import UpdateProposalCommand
from app.application.dtos.finance import (
    KEY_APPROVAL_MEETING_ID,
    KEY_ASSETS,
    KEY_BILLS,
    KEY_BUDGET_HEAD,
    KEY_COMPARATIVE,
    KEY_DEPARTMENT,
    KEY_ESTIMATED_COST,
    KEY_MINUTES,
    KEY_NOTES,
    KEY_PRIORITY,
    KEY_PROPOSAL_DATE,
    KEY_PROPOSAL_NUMBER,
    KEY_PROPOSAL_STATUS,
    KEY_PURCHASE_ORDERS,
    KEY_PURPOSE,
    KEY_QUOTATIONS,
    KEY_RECOMMENDATIONS,
    KEY_REQUESTED_BY,
    KEY_REQUESTED_NAME,
    KEY_TAGS,
    ProposalOutput,
    finance_edge_group,
    parse_amount,
)
from app.application.exceptions import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
)
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.finance.create_proposal import (
    SECTION_KEYS,
    assert_approval_meeting,
    assert_document_refs,
    assert_link_targets,
    assert_requester,
    assert_vendor_refs,
    find_proposal_duplicates,
)
from app.application.use_cases.finance.helpers import (
    enrich_proposal_output,
    normalise_section_rows,
)
from app.application.validators.finance import assert_valid_update_proposal_input
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

_SECTION_META_KEY = {
    "quotations": KEY_QUOTATIONS,
    "comparative": KEY_COMPARATIVE,
    "purchase_orders": KEY_PURCHASE_ORDERS,
    "bills": KEY_BILLS,
    "assets": KEY_ASSETS,
}


class UpdateProposalUseCase:
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

    def execute(self, command: UpdateProposalCommand) -> ProposalOutput:
        data = command.input
        assert_valid_update_proposal_input(data)
        obj = self._repository.get_by_id(command.object_id)
        if obj is None or obj.object_type is not ObjectType.PURCHASE:
            raise ObjectNotFoundError(f"Purchase proposal {command.object_id} not found.")

        actor = data.actor.strip()
        meta = {entry.key: entry.value for entry in obj.metadata.entries}

        if any(
            value is not None
            for value in (data.title, data.proposal_number, data.department, data.proposal_date)
        ):
            duplicates = find_proposal_duplicates(
                self._repository,
                title=data.title if data.title is not None else obj.title,
                proposal_number=(
                    data.proposal_number
                    if data.proposal_number is not None
                    else meta.get(KEY_PROPOSAL_NUMBER)
                ),
                department=(
                    data.department if data.department is not None else meta.get(KEY_DEPARTMENT)
                ),
                proposal_date=(
                    data.proposal_date
                    if data.proposal_date is not None
                    else meta.get(KEY_PROPOSAL_DATE)
                ),
                exclude_id=str(obj.id),
            )
            if duplicates:
                raise ObjectAlreadyExistsError(
                    f"Duplicate purchase proposal: {duplicates[0].id} ({duplicates[0].title!r}) "
                    f"already carries this number / title+department+date."
                )

        # Section group-replaces are validated against live vendors/documents.
        for section in SECTION_KEYS:
            payload = getattr(data, section)
            if payload is not None:
                assert_vendor_refs(self._repository, payload)
                assert_document_refs(self._repository, payload)
        requested_name: str | None = None
        if data.requested_by is not None:
            requested_name = assert_requester(self._repository, data.requested_by)
        if data.approval_meeting_id is not None:
            assert_approval_meeting(self._repository, data.approval_meeting_id)

        if data.title is not None and data.title.strip() != obj.title:
            obj.rename(data.title, actor)
        if data.status is not None and data.status != obj.status:
            obj.change_status(data.status, actor)

        for key, value in (
            (KEY_PROPOSAL_NUMBER, data.proposal_number),
            (KEY_DEPARTMENT, data.department),
            (KEY_PROPOSAL_DATE, data.proposal_date),
            (KEY_PURPOSE, data.purpose),
            (KEY_BUDGET_HEAD, data.budget_head),
            (KEY_PROPOSAL_STATUS, data.proposal_status),
            (KEY_PRIORITY, data.priority),
            (KEY_NOTES, data.notes),
            (KEY_MINUTES, data.minutes),
            (KEY_RECOMMENDATIONS, data.recommendations),
            (KEY_APPROVAL_MEETING_ID, data.approval_meeting_id),
        ):
            if value is not None:
                self._set(obj, key, str(value), actor)

        if data.estimated_cost is not None:
            cost = parse_amount(data.estimated_cost)
            self._set(obj, KEY_ESTIMATED_COST, "" if cost is None else str(cost), actor)
        if data.requested_by is not None:
            self._set(obj, KEY_REQUESTED_BY, str(data.requested_by).strip(), actor)
            self._set(obj, KEY_REQUESTED_NAME, requested_name or "", actor)
        if data.tags is not None:
            self._set(obj, KEY_TAGS, json.dumps(data.tags, ensure_ascii=False), actor)
        for section in SECTION_KEYS:
            payload = getattr(data, section)
            if payload is not None:
                rows = normalise_section_rows(section, list(payload))
                self._set(
                    obj, _SECTION_META_KEY[section], json.dumps(rows, ensure_ascii=False), actor
                )

        # Link groups — group-replaces (the committees PART 7 precedent).
        link_payloads = {
            "projects": data.projects,
            "grants": data.grants,
            "committees": data.committees,
        }
        for group, raw in link_payloads.items():
            if raw is None:
                continue
            new_ids = {ObjectId.parse(item) for item in raw}
            assert_link_targets(self._repository, group, sorted(new_ids, key=str))
            existing = {
                rel.target: rel
                for rel in obj.relationships
                if rel.kind is RelationshipKind.RELATED_TO
                and finance_edge_group(rel.kind, self._type_of(rel.target)) == group
            }
            for target, _rel in list(existing.items()):
                if target not in new_ids:
                    obj.remove_relationship(target, RelationshipKind.RELATED_TO, actor=actor)
            for target_id in sorted(new_ids, key=str):
                if target_id not in existing:
                    obj.add_relationship(
                        target_id, RelationshipKind.RELATED_TO, Provenance.ASSERTED, actor=actor
                    )

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        link_ids = [
            rel.target for rel in obj.relationships
            if rel.kind is RelationshipKind.RELATED_TO
        ]
        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(link_ids)}
        output = ProposalOutput.from_domain(obj, events, linked_by_id=linked_by_id)
        enrich_proposal_output(self._repository, obj, output)
        return output

    def _type_of(self, target) -> ObjectType | None:
        found = self._repository.get_by_id(target)
        return found.object_type if found is not None else None
