"""Use case: Register a Purchase Proposal (PART 1 directory + PART 2
committee linkage + PARTS 4-8 sections + link groups).

Mirrors ``CreateCommitteeUseCase``: validate -> duplicate scan (proposal
number; title+department+proposal_date triple, 409) -> link target
assertions (422) -> vendor/faculty/meeting reference assertions (422) ->
L6 metadata record -> RELATED_TO edges on the proposal aggregate -> persist
-> events -> enriched output (one shared enrichment helper, no copies).
"""
from __future__ import annotations

import json

from app.application.commands.create_proposal import CreateProposalCommand
from app.application.dtos.finance import (
    FINANCE_GROUP_TARGET_TYPE,
    FINANCE_LINK_GROUPS,
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
    parse_amount,
)
from app.application.exceptions import ObjectAlreadyExistsError, ValidationError
from app.application.ports.event_publisher import DomainEventPublisher
from app.application.use_cases.finance.helpers import (
    enrich_proposal_output,
    normalise_section_rows,
)
from app.application.validators.finance import assert_valid_create_proposal_input
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import (
    MetadataLayer,
    ObjectType,
    Provenance,
    RelationshipKind,
)
from app.domain.value_objects.metadata import Metadata, MetadataEntry
from app.domain.value_objects.object_id import ObjectId

SECTION_KEYS = ("quotations", "comparative", "purchase_orders", "bills", "assets")


def find_proposal_duplicates(
    repository: ObjectRepository,
    *,
    title: str | None,
    proposal_number: str | None,
    department: str | None,
    proposal_date: str | None,
    exclude_id: str | None = None,
) -> list[UniversalObject]:
    """Registry duplicate detection: proposal number, else the
    (title, department, proposal_date) triple."""
    wanted_number = (proposal_number or "").strip().casefold()
    wanted_title = (title or "").strip().casefold()
    wanted_dept = (department or "").strip().casefold()
    wanted_date = (proposal_date or "").strip()
    if not (wanted_number or wanted_title):
        return []
    matches: list[UniversalObject] = []
    for obj in repository.find_by_type(ObjectType.PURCHASE):
        if exclude_id is not None and str(obj.id) == exclude_id:
            continue
        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        if wanted_number and (
            meta.get(KEY_PROPOSAL_NUMBER) or ""
        ).strip().casefold() == wanted_number:
            matches.append(obj)
            continue
        if (
            wanted_title
            and wanted_date
            and obj.title.strip().casefold() == wanted_title
            and (meta.get(KEY_DEPARTMENT) or "").strip().casefold() == wanted_dept
            and (meta.get(KEY_PROPOSAL_DATE) or "").strip() == wanted_date
        ):
            matches.append(obj)
    return matches


def assert_link_targets(
    repository: ObjectRepository, group: str, ids: list[ObjectId]
) -> None:
    """Linked Objects must exist and carry the group's expected type (422)."""
    expected = FINANCE_GROUP_TARGET_TYPE[group]
    for target_id in ids:
        target = repository.get_by_id(target_id)
        if target is None:
            raise ValidationError(f"Linked object {target_id} not found.")
        if target.object_type is not expected:
            raise ValidationError(
                f"{group} expects {expected.value} targets; {target_id} is a "
                f"{target.object_type.value}."
            )


def assert_vendor_refs(repository: ObjectRepository, rows: list[dict]) -> None:
    """Every section vendor_id must resolve to a live VENDOR Object (422)."""
    for row in rows:
        raw = row.get("vendor_id")
        if raw in (None, ""):
            continue  # presence is enforced by the validators where required
        target_id = ObjectId.parse(str(raw).strip())
        target = repository.get_by_id(target_id)
        if target is None:
            raise ValidationError(f"Vendor {target_id} not found.")
        if target.object_type is not ObjectType.VENDOR:
            raise ValidationError(
                f"Vendor {target_id} must be a vendor object; it is a "
                f"{target.object_type.value}."
            )


def assert_requester(repository: ObjectRepository, requested_by: str | None) -> str | None:
    """Requested-by must be a live FACULTY Object (422); returns its title."""
    if requested_by in (None, ""):
        return None
    target_id = ObjectId.parse(str(requested_by).strip())
    target = repository.get_by_id(target_id)
    if target is None:
        raise ValidationError(f"Requester {target_id} not found.")
    if target.object_type is not ObjectType.FACULTY:
        raise ValidationError(
            f"requested_by must reference a faculty object; {target_id} is a "
            f"{target.object_type.value}."
        )
    return target.title


def assert_approval_meeting(repository: ObjectRepository, meeting_id: str | None) -> None:
    """Approval meeting must be a live MEETING Object (422)."""
    if meeting_id in (None, ""):
        return
    target_id = ObjectId.parse(str(meeting_id).strip())
    target = repository.get_by_id(target_id)
    if target is None:
        raise ValidationError(f"Approval meeting {target_id} not found.")
    if target.object_type is not ObjectType.MEETING:
        raise ValidationError(
            f"approval_meeting_id must reference a meeting object; {target_id} is a "
            f"{target.object_type.value}."
        )


def assert_document_refs(repository: ObjectRepository, rows: list[dict]) -> None:
    """Section document_ids must resolve to live DOCUMENT Objects (422)."""
    for row in rows:
        for raw in row.get("document_ids") or []:
            target_id = ObjectId.parse(str(raw).strip())
            target = repository.get_by_id(target_id)
            if target is None:
                raise ValidationError(f"Document {target_id} not found.")
            if target.object_type is not ObjectType.DOCUMENT:
                raise ValidationError(
                    f"document_ids must reference document objects; {target_id} is a "
                    f"{target.object_type.value}."
                )


def all_section_rows(data) -> list[dict]:
    rows: list[dict] = []
    for section in SECTION_KEYS:
        rows.extend(list(getattr(data, section) or []))
    return rows


class CreateProposalUseCase:
    def __init__(
        self,
        repository: ObjectRepository,
        event_publisher: DomainEventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    def execute(self, command: CreateProposalCommand) -> ProposalOutput:
        data = command.input
        assert_valid_create_proposal_input(data)

        duplicates = find_proposal_duplicates(
            self._repository,
            title=data.title,
            proposal_number=data.proposal_number,
            department=data.department,
            proposal_date=data.proposal_date,
        )
        if duplicates:
            existing = duplicates[0]
            raise ObjectAlreadyExistsError(
                f"Duplicate purchase proposal: {existing.id} ({existing.title!r}) already "
                f"carries this number / title+department+date."
            )

        link_ids: dict[str, list[ObjectId]] = {}
        for group in FINANCE_LINK_GROUPS:
            raw_ids = list(getattr(data, group) or [])
            ids = [ObjectId.parse(raw) for raw in raw_ids]
            assert_link_targets(self._repository, group, ids)
            link_ids[group] = ids

        sections = {
            section: normalise_section_rows(section, list(getattr(data, section) or []))
            for section in SECTION_KEYS
        }
        rows = [row for section_rows_ in sections.values() for row in section_rows_]
        assert_vendor_refs(self._repository, rows)
        assert_document_refs(self._repository, rows)
        requested_name = assert_requester(self._repository, data.requested_by)
        assert_approval_meeting(self._repository, data.approval_meeting_id)

        entries: list[MetadataEntry] = []

        def put(key: str, value: object) -> None:
            if value is None or str(value) == "":
                return
            entries.append(
                MetadataEntry(key, str(value), MetadataLayer.L6_HUMAN_ASSERTED, Provenance.ASSERTED)
            )

        put(KEY_PROPOSAL_NUMBER, data.proposal_number)
        put(KEY_DEPARTMENT, data.department)
        put(KEY_REQUESTED_BY, data.requested_by)
        put(KEY_REQUESTED_NAME, requested_name)
        put(KEY_PROPOSAL_DATE, data.proposal_date)
        put(KEY_PURPOSE, data.purpose)
        put(KEY_BUDGET_HEAD, data.budget_head)
        cost = parse_amount(data.estimated_cost)
        if cost is not None:
            put(KEY_ESTIMATED_COST, str(cost))
        put(KEY_PROPOSAL_STATUS, data.proposal_status or "draft")
        put(KEY_PRIORITY, data.priority)
        put(KEY_NOTES, data.notes)
        put(KEY_TAGS, json.dumps(data.tags, ensure_ascii=False) if data.tags else None)
        put(KEY_APPROVAL_MEETING_ID, data.approval_meeting_id)
        put(KEY_MINUTES, data.minutes)
        put(KEY_RECOMMENDATIONS, data.recommendations)
        for section in SECTION_KEYS:
            if sections[section]:
                put(
                    {
                        "quotations": KEY_QUOTATIONS,
                        "comparative": KEY_COMPARATIVE,
                        "purchase_orders": KEY_PURCHASE_ORDERS,
                        "bills": KEY_BILLS,
                        "assets": KEY_ASSETS,
                    }[section],
                    json.dumps(sections[section], ensure_ascii=False),
                )

        obj = UniversalObject.create(
            object_type=ObjectType.PURCHASE,
            title=data.title.strip(),
            created_by=data.created_by.strip(),
            status=data.status,
            metadata=Metadata(entries=tuple(entries)),
        )
        all_link_ids: list[ObjectId] = []
        for group in FINANCE_LINK_GROUPS:
            for target_id in link_ids[group]:
                obj.add_relationship(
                    target_id, RelationshipKind.RELATED_TO, Provenance.ASSERTED,
                    actor=data.created_by.strip(),
                )
                all_link_ids.append(target_id)

        self._repository.save(obj)
        events = obj.pop_domain_events()
        if self._event_publisher is not None:
            self._event_publisher.publish(events)

        linked_by_id = {str(o.id): o for o in self._repository.find_by_ids(all_link_ids)}
        output = ProposalOutput.from_domain(obj, events, linked_by_id=linked_by_id)
        enrich_proposal_output(self._repository, obj, output)
        return output
