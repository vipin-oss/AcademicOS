"""Shared helpers for the Finance & Procurement use cases.

Mirrors ``use_cases/committees/helpers.py`` + ``use_cases/research/helpers``
one-to-one: section-row normalisers (the ``_normalise_member_rows``
precedent), vendor/document/approval-meeting resolution (the
``get_meeting`` supporting-documents precedent), computed proposal/vendor
stats, the PART 11 dashboard aggregation, the PART 9 budget lens composed
over the frozen research helpers, and the PART 8 asset-register collector.
"""
from __future__ import annotations

from app.application.dtos.finance import (
    ACTIVE_PROPOSAL_STATUSES,
    ASSET_ROW_KEYS,
    BILL_ROW_KEYS,
    COMPARATIVE_ROW_KEYS,
    FINANCE_LINK_GROUPS,
    KEY_ASSETS,
    KEY_BILLS,
    KEY_COMPARATIVE,
    KEY_PROPOSAL_NUMBER,
    KEY_PROPOSAL_STATUS,
    KEY_PURCHASE_ORDERS,
    KEY_QUOTATIONS,
    PENDING_APPROVAL_STATUSES,
    PURCHASE_ORDER_ROW_KEYS,
    QUOTATION_ROW_KEYS,
    AssetRegisterRow,
    MeetingRefOutput,
    ProposalOutput,
    parse_json_object_list,
)
from app.application.use_cases.research.helpers import (
    grant_totals,
    grants_of_project,
    project_budget,
)
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType, RelationshipKind

SECTION_ROW_KEYS: dict[str, tuple[str, ...]] = {
    "quotations": QUOTATION_ROW_KEYS,
    "comparative": COMPARATIVE_ROW_KEYS,
    "purchase_orders": PURCHASE_ORDER_ROW_KEYS,
    "bills": BILL_ROW_KEYS,
    "assets": ASSET_ROW_KEYS,
}


def _meta(obj: UniversalObject) -> dict[str, str]:
    return {entry.key: entry.value for entry in obj.metadata.entries}


# ---------------------------------------------------------------------------
# Row normalisers (unknown keys dropped; strings trimmed; recommended flag
# normalised; numbers remain wire strings — parse on read)
# ---------------------------------------------------------------------------
def normalise_section_rows(section: str, rows: list[dict]) -> list[dict]:
    whitelist = SECTION_ROW_KEYS[section]
    out: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        clean = {key: row[key] for key in whitelist if key in row and row[key] not in (None,)}
        for key, value in list(clean.items()):
            if isinstance(value, str):
                value = value.strip()
                if value == "":
                    del clean[key]
                    continue
                clean[key] = value
        if section == "comparative" and "recommended" in clean:
            clean["recommended"] = bool(
                clean["recommended"] not in (None, "", False, "no", "false")
            )
        if "document_ids" in clean:
            clean["document_ids"] = [str(raw) for raw in (clean["document_ids"] or [])]
        out.append(clean)
    return out


def section_rows(meta: dict[str, str], key: str) -> list[dict]:
    return parse_json_object_list(meta.get(key))


# ---------------------------------------------------------------------------
# Money maths (wire strings -> floats; research parse_amount duck-types both)
# ---------------------------------------------------------------------------
def _money(value) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def bill_total(row: dict) -> float:
    """Bill value = amount + gst_amount (GST rides as its own column)."""
    return round(_money(row.get("amount")) + _money(row.get("gst_amount")), 2)


def paid_bill_total(row: dict) -> float:
    return bill_total(row) if (row.get("payment_status") or "pending") == "paid" else 0.0


def proposal_spent(meta: dict[str, str]) -> float:
    """Procurement spend on a proposal = sum of PAID bill totals."""
    return round(sum(paid_bill_total(row) for row in section_rows(meta, KEY_BILLS)), 2)


def proposal_committed(meta: dict[str, str]) -> float:
    """Committed = sum of non-cancelled purchase-order amounts."""
    return round(
        sum(
            _money(row.get("amount"))
            for row in section_rows(meta, KEY_PURCHASE_ORDERS)
            if (row.get("status") or "issued") != "cancelled"
        ),
        2,
    )


def proposal_stats(meta: dict[str, str]) -> dict[str, int | float]:
    quotations = section_rows(meta, KEY_QUOTATIONS)
    orders = section_rows(meta, KEY_PURCHASE_ORDERS)
    bills = section_rows(meta, KEY_BILLS)
    assets = section_rows(meta, KEY_ASSETS)
    return {
        "quotations": len(quotations),
        "purchase_orders": len(orders),
        "bills": len(bills),
        "pending_bills": sum(
            1 for row in bills if (row.get("payment_status") or "pending") != "paid"
        ),
        "committed": proposal_committed(meta),
        "spent": proposal_spent(meta),
        "assets": len(assets),
    }


# ---------------------------------------------------------------------------
# Resolution (vendor names, supporting documents, approval meeting)
# ---------------------------------------------------------------------------
def resolve_vendors(
    repository: ObjectRepository, rows: list[dict]
) -> dict[str, str]:
    """vendor_id -> vendor title for every row across sections."""
    ids = sorted(
        {str(row.get("vendor_id")) for row in rows if row.get("vendor_id")}
    )
    if not ids:
        return {}
    found = repository.find_by_ids(ids)
    return {
        str(obj.id): obj.title
        for obj in found
        if obj.object_type is ObjectType.VENDOR
    }


def annotate_proposal_sections(
    repository: ObjectRepository, output: ProposalOutput
) -> None:
    """In-place: vendor_name + supporting_documents on every section row."""
    all_rows = (
        output.quotations
        + output.comparative
        + output.purchase_orders
        + output.bills
        + output.assets
    )
    names = resolve_vendors(repository, all_rows)
    document_ids = sorted(
        {
            str(raw)
            for row in all_rows
            for raw in (row.get("document_ids") or [])
        }
    )
    docs_by_id = (
        {str(doc.id): doc for doc in repository.find_by_ids(document_ids)}
        if document_ids
        else {}
    )
    for row in all_rows:
        name = names.get(str(row.get("vendor_id") or ""))
        if name is not None:
            row["vendor_name"] = name
        if "document_ids" in row:
            row["supporting_documents"] = [
                {"id": str(found.id), "title": found.title}
                for raw in (row.get("document_ids") or [])
                if (found := docs_by_id.get(str(raw))) is not None
            ]


def resolve_approval_meeting(
    repository: ObjectRepository, meeting_id: str | None
) -> MeetingRefOutput | None:
    if not meeting_id:
        return None
    meeting = repository.get_by_id(meeting_id)
    if meeting is None or meeting.object_type is not ObjectType.MEETING:
        return None
    meta = _meta(meeting)
    return MeetingRefOutput(
        id=str(meeting.id),
        title=meeting.title,
        meeting_number=meta.get("meeting_number"),
        meeting_date=meta.get("meeting_date"),
        mode=meta.get("mode"),
        venue=meta.get("venue"),
    )


def enrich_proposal_output(
    repository: ObjectRepository, obj: UniversalObject, output: ProposalOutput
) -> None:
    """The one shared proposal enrichment (the ``enrich_committee_output``
    precedent): resolved vendor names + supporting documents on every
    section row, the resolved PART 2 approval meeting, normalised link-group
    keys, and the computed stats block."""
    meta = _meta(obj)
    output.links = {group: output.links.get(group, []) for group in FINANCE_LINK_GROUPS}
    annotate_proposal_sections(repository, output)
    output.approval_meeting = resolve_approval_meeting(
        repository, output.approval_meeting_id
    )
    output.stats = proposal_stats(meta)


def proposals_of_vendor(
    repository: ObjectRepository, vendor_id: str
) -> list[UniversalObject]:
    """Every purchase proposal whose sections reference this vendor."""
    out = []
    for obj in repository.find_by_type(ObjectType.PURCHASE):
        meta = _meta(obj)
        rows = (
            section_rows(meta, KEY_QUOTATIONS)
            + section_rows(meta, KEY_COMPARATIVE)
            + section_rows(meta, KEY_PURCHASE_ORDERS)
            + section_rows(meta, KEY_BILLS)
        )
        if any(str(row.get("vendor_id") or "") == vendor_id for row in rows):
            out.append(obj)
    out.sort(key=lambda obj: (obj.title.casefold(), str(obj.id)))
    return out


def vendor_stats(repository: ObjectRepository, vendor_id: str) -> dict[str, int | float]:
    proposals = proposals_of_vendor(repository, vendor_id)
    orders = 0
    pending = 0
    spent = 0.0
    for obj in proposals:
        meta = _meta(obj)
        for row in section_rows(meta, KEY_PURCHASE_ORDERS):
            if str(row.get("vendor_id") or "") == vendor_id:
                orders += 1
        for row in section_rows(meta, KEY_BILLS):
            if str(row.get("vendor_id") or "") == vendor_id:
                spent += paid_bill_total(row)
                if (row.get("payment_status") or "pending") != "paid":
                    pending += 1
    return {
        "proposals": len(proposals),
        "purchase_orders": orders,
        "pending_bills": pending,
        "spent": round(spent, 2),
    }


# ---------------------------------------------------------------------------
# Proposal collectors used by the budget lens / dashboards
# ---------------------------------------------------------------------------
def all_proposals(repository: ObjectRepository) -> list[UniversalObject]:
    return repository.find_by_type(ObjectType.PURCHASE)


def proposals_linked_to(
    repository: ObjectRepository, target_id: str
) -> list[UniversalObject]:
    """Proposals carrying a RELATED_TO edge to the given link target."""
    return [
        obj
        for obj in all_proposals(repository)
        if any(
            rel.kind is RelationshipKind.RELATED_TO and str(rel.target) == target_id
            for rel in obj.relationships
        )
    ]


# ---------------------------------------------------------------------------
# PART 9 — Budget tracking (project lens, composed read)
# ---------------------------------------------------------------------------
def budget_line_for_project(
    repository: ObjectRepository, project: UniversalObject
) -> dict:
    """Approved/released from the frozen research helpers; procurement spend
    (PAID bills on proposals linked to this project) is added into utilized —
    a composed read, nothing stored."""
    budget = project_budget(repository, project)
    linked = proposals_linked_to(repository, str(project.id))
    spent = round(sum(proposal_spent(_meta(obj)) for obj in linked), 2)
    base_utilized = budget["utilized"] or 0.0
    utilized = round(base_utilized + spent, 2)
    approved = budget["approved"]
    remaining = round(approved - utilized, 2) if approved is not None else None
    return {
        "project_id": str(project.id),
        "title": project.title,
        "approved": approved,
        "released": budget.get("grants_released") or 0.0,
        "utilized": utilized,
        "remaining": remaining,
        "proposals": len(linked),
        "spent": spent,
    }


# ---------------------------------------------------------------------------
# PART 8 — Asset register collector
# ---------------------------------------------------------------------------
def asset_register_rows(repository: ObjectRepository) -> list[AssetRegisterRow]:
    rows: list[AssetRegisterRow] = []
    for obj in all_proposals(repository):
        meta = _meta(obj)
        for row in section_rows(meta, KEY_ASSETS):
            rows.append(
                AssetRegisterRow(
                    proposal_id=str(obj.id),
                    proposal_number=meta.get(KEY_PROPOSAL_NUMBER),
                    proposal_title=obj.title,
                    row=dict(row),
                )
            )
    rows.sort(
        key=lambda item: (
            str(item.row.get("item_name") or "").casefold(),
            str(item.row.get("asset_id") or ""),
            item.proposal_id,
        )
    )
    return rows


# ---------------------------------------------------------------------------
# Indian financial-year helpers (PART 12) — FY YYYY-YY runs April..March
# ---------------------------------------------------------------------------
def financial_year_bounds(financial_year: str) -> tuple[str, str]:
    start = int(financial_year[:4])
    return (f"{start}-04-01", f"{start + 1}-03-31")


def financial_year_of(date_str: str | None) -> str | None:
    if not date_str or len(date_str) < 7:
        return None
    try:
        year = int(date_str[:4])
        month = int(date_str[5:7])
    except ValueError:
        return None
    start = year if month >= 4 else year - 1
    return f"{start}-{str((start + 1) % 100).zfill(2)}"


# ---------------------------------------------------------------------------
# PART 11 — Dashboard cards (computed read)
# ---------------------------------------------------------------------------
def finance_dashboard(repository: ObjectRepository) -> dict:
    proposals = all_proposals(repository)
    active = 0
    pending_approvals = 0
    purchase_orders = 0
    pending_bills = 0
    procurement_spent = 0.0
    for obj in proposals:
        meta = _meta(obj)
        status = meta.get(KEY_PROPOSAL_STATUS) or "draft"
        if status in ACTIVE_PROPOSAL_STATUSES:
            active += 1
        if status in PENDING_APPROVAL_STATUSES:
            pending_approvals += 1
        for row in section_rows(meta, KEY_PURCHASE_ORDERS):
            if (row.get("status") or "issued") != "cancelled":
                purchase_orders += 1
        for row in section_rows(meta, KEY_BILLS):
            if (row.get("payment_status") or "pending") != "paid":
                pending_bills += 1
        procurement_spent += proposal_spent(meta)

    vendors = repository.find_by_type(ObjectType.VENDOR)

    # Global budget position = frozen research project budgets + procurement
    # spend overlapping only via PAID bills (research records its own
    # expenditures separately; procurement tracks what purchasing paid out).
    approved_total = 0.0
    approved_seen = False
    research_utilized = 0.0
    for project in repository.find_by_type(ObjectType.RESEARCH_PROJECT):
        budget = project_budget(repository, project)
        if budget["approved"] is not None:
            approved_total += budget["approved"]
            approved_seen = True
        research_utilized += budget["utilized"] or 0.0

    utilized = round(research_utilized + procurement_spent, 2)
    remaining = round(approved_total - utilized, 2) if approved_seen else None
    return {
        "active_procurements": active,
        "pending_approvals": pending_approvals,
        "total_vendors": len(vendors),
        "total_purchase_orders": purchase_orders,
        "budget_utilized": utilized,
        "budget_remaining": remaining,
        "pending_bills": pending_bills,
    }


# Re-export the frozen research collectors so the use cases have a single
# local import surface (the committees helpers mirror).
__all__ = [
    "grant_totals",
    "grants_of_project",
    "project_budget",
]
