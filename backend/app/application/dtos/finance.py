"""DTOs and metadata-key catalogue for the Finance & Procurement slice.

Mirrors ``dtos/committee.py`` one-to-one: every field rides as L6
human-asserted metadata on Universal Objects; no new DB models, no enum
changes beyond the doctrine-sanctioned ``ObjectType.VENDOR`` append.

Two record kinds:
  - Vendor            -> ``ObjectType.VENDOR`` (registry; GST/name unique)
  - Purchase Proposal -> ``ObjectType.PURCHASE`` with JSON list-of-dicts
    sections (quotations / comparative / purchase_orders / bills / assets),
    the committee ``members`` / meeting ``agenda_items`` precedent.

Link groups to the research & governance graph ride as RELATED_TO edges on
the proposal aggregate (the committees PART 7 precedent); the budget lens
(PART 9) is a read-only composition over the frozen research helpers.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.application.dtos.publication import parse_json_list  # noqa: F401  (re-export)
from app.application.dtos.research import (
    format_amount,  # noqa: F401  (re-export)
    link_dict,  # noqa: F401  (re-export)
    linked_target_ids,  # noqa: F401  (re-export)
    parse_amount,  # noqa: F401  (re-export)
    parse_json_object_list,  # noqa: F401  (re-export)
)
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType, RelationshipKind

# ---------------------------------------------------------------------------
# Metadata keys — Vendor registry (PART 3)
# ---------------------------------------------------------------------------
KEY_GST_NUMBER = "gst_number"  # unique when provided (409 on duplicate)
KEY_PAN = "pan"
KEY_CONTACT_PERSON = "contact_person"
KEY_EMAIL = "email"
KEY_PHONE = "phone"
KEY_ADDRESS = "address"
KEY_BANK_DETAILS = "bank_details"  # JSON dict {bank_name, account_number, ifsc, branch}
KEY_NOTES = "notes"
KEY_TAGS = "tags"  # JSON list of strings

# ---------------------------------------------------------------------------
# Metadata keys — Purchase Proposal (PART 1) + committee linkage (PART 2)
# ---------------------------------------------------------------------------
KEY_PROPOSAL_NUMBER = "proposal_number"  # unique when provided (409 on duplicate)
KEY_DEPARTMENT = "department"
KEY_REQUESTED_BY = "requested_by"  # faculty object id (assignee precedent)
KEY_REQUESTED_NAME = "requested_name"  # snapshot resolved at write time
KEY_PROPOSAL_DATE = "proposal_date"
KEY_PURPOSE = "purpose"
KEY_BUDGET_HEAD = "budget_head"
KEY_ESTIMATED_COST = "estimated_cost"  # decimal string
KEY_PROPOSAL_STATUS = "proposal_status"  # business lifecycle (metadata vocab)
KEY_PRIORITY = "priority"
KEY_MINUTES = "minutes"  # approval-minutes text (PART 2)
KEY_RECOMMENDATIONS = "recommendations"
KEY_APPROVAL_MEETING_ID = "approval_meeting_id"  # MEETING object id (PART 2)

# JSON list-of-dicts sections (PARTS 4/5/6/7/8) — row shapes documented at
# the vocabularies below; extra keys are dropped by the normalisers.
KEY_QUOTATIONS = "quotations"
KEY_COMPARATIVE = "comparative"
KEY_PURCHASE_ORDERS = "purchase_orders"
KEY_BILLS = "bills"
KEY_ASSETS = "assets"

# ---------------------------------------------------------------------------
# Vocabularies (metadata-level — the universal ObjectStatus lifecycle stays
# draft/active/archived; these ride as human-asserted strings)
# ---------------------------------------------------------------------------
PROPOSAL_STATUSES = (
    "draft",
    "submitted",
    "under_review",
    "approved",
    "rejected",
    "ordered",
    "completed",
    "cancelled",
)
# Statuses that count as an "active procurement" on the PART 11 dashboard.
ACTIVE_PROPOSAL_STATUSES = ("submitted", "under_review", "approved", "ordered")
PENDING_APPROVAL_STATUSES = ("submitted", "under_review")
PROPOSAL_PRIORITIES = ("high", "medium", "low")
PO_STATUSES = ("issued", "acknowledged", "partially_received", "delivered", "closed", "cancelled")
PAYMENT_STATUSES = ("pending", "partial", "paid")
COMPLIANCE_VALUES = ("compliant", "non_compliant", "conditional")
ASSET_STATUSES = ("in_service", "in_store", "under_maintenance", "retired")
ASSET_CATEGORIES = (
    "equipment",
    "furniture",
    "computer",
    "laboratory",
    "library",
    "vehicle",
    "software",
    "other",
)

# Section row whitelists (unknown keys dropped — the _normalise_member_rows
# precedent from the committees module).
QUOTATION_ROW_KEYS = (
    "vendor_id",
    "quotation_date",
    "amount",
    "validity_date",
    "document_ids",
    "remarks",
)
COMPARATIVE_ROW_KEYS = (
    "vendor_id",
    "amount",
    "technical_compliance",
    "financial_compliance",
    "recommended",
    "remarks",
)
PURCHASE_ORDER_ROW_KEYS = (
    "po_number",
    "po_date",
    "vendor_id",
    "amount",
    "status",
    "delivery_date",
    "document_ids",
    "remarks",
)
BILL_ROW_KEYS = (
    "bill_number",
    "invoice_number",
    "vendor_id",
    "bill_date",
    "amount",
    "gst_amount",
    "payment_status",
    "paid_date",
    "po_number",
    "document_ids",
    "remarks",
)
ASSET_ROW_KEYS = (
    "asset_id",
    "category",
    "item_name",
    "serial_number",
    "location",
    "assigned_to",
    "warranty_expiry",
    "purchase_date",
    "cost",
    "status",
    "po_number",
    "remarks",
)

# ---------------------------------------------------------------------------
# Link groups — proposal ↔ research/governance graph (committees precedent)
# ---------------------------------------------------------------------------
FINANCE_GROUP_TO_KIND: dict[str, RelationshipKind] = {
    "projects": RelationshipKind.RELATED_TO,
    "grants": RelationshipKind.RELATED_TO,
    "committees": RelationshipKind.RELATED_TO,
}
FINANCE_LINK_GROUPS = tuple(FINANCE_GROUP_TO_KIND.keys())

FINANCE_GROUP_TARGET_TYPE: dict[str, ObjectType] = {
    "projects": ObjectType.RESEARCH_PROJECT,
    "grants": ObjectType.GRANT,
    "committees": ObjectType.COMMITTEE,
}

_GROUP_TARGET_TO_GROUP: dict[ObjectType, str] = {
    ObjectType.RESEARCH_PROJECT: "projects",
    ObjectType.GRANT: "grants",
    ObjectType.COMMITTEE: "committees",
}


def finance_edge_group(kind: RelationshipKind, target_type: ObjectType) -> str | None:
    """The finance link group an outgoing proposal edge belongs to."""
    if kind is RelationshipKind.RELATED_TO:
        return _GROUP_TARGET_TO_GROUP.get(target_type)
    return None


def grouped_finance_links(
    obj: UniversalObject, linked_by_id: dict[str, UniversalObject]
) -> dict[str, list[dict]]:
    links: dict[str, list[dict]] = {group: [] for group in FINANCE_LINK_GROUPS}
    for rel in obj.relationships:
        target = linked_by_id.get(str(rel.target))
        if target is None:
            continue
        group = finance_edge_group(rel.kind, target.object_type)
        if group is not None:
            links[group].append(link_dict(target, rel.kind))
    return links


def parse_json_object(raw: str | None) -> dict:
    """Parse a JSON object metadata value ({} when unset/invalid)."""
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


# ---------------------------------------------------------------------------
# Boundary inputs
# ---------------------------------------------------------------------------
@dataclass
class CreateVendorInput:
    name: str  # -> Object title (unique, 409 on duplicate)
    created_by: str
    status: ObjectStatus = ObjectStatus.ACTIVE
    gst_number: str | None = None
    pan: str | None = None
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    bank_details: dict = field(default_factory=dict)
    notes: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class UpdateVendorInput:
    """Partial update — None = untouched; a provided value replaces."""

    actor: str
    name: str | None = None
    status: ObjectStatus | None = None
    gst_number: str | None = None
    pan: str | None = None
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    bank_details: dict | None = None
    notes: str | None = None
    tags: list[str] | None = None


@dataclass
class CreateProposalInput:
    title: str  # -> Object title (Proposal Title)
    created_by: str
    status: ObjectStatus = ObjectStatus.DRAFT
    proposal_number: str | None = None
    department: str | None = None
    requested_by: str | None = None  # faculty object id
    proposal_date: str | None = None
    purpose: str | None = None
    budget_head: str | None = None
    estimated_cost: str | None = None  # decimal string
    proposal_status: str = "draft"
    priority: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    # PART 2 procurement committee linkage.
    approval_meeting_id: str | None = None
    minutes: str | None = None
    recommendations: str | None = None
    # PARTS 4-8 sections (list-of-dicts rows, whitelisted shapes).
    quotations: list[dict] = field(default_factory=list)
    comparative: list[dict] = field(default_factory=list)
    purchase_orders: list[dict] = field(default_factory=list)
    bills: list[dict] = field(default_factory=list)
    assets: list[dict] = field(default_factory=list)
    # Link groups (RELATED_TO edges on the proposal aggregate).
    projects: list[str] = field(default_factory=list)
    grants: list[str] = field(default_factory=list)
    committees: list[str] = field(default_factory=list)


@dataclass
class UpdateProposalInput:
    """Partial update — None = untouched; a provided value replaces."""

    actor: str
    title: str | None = None
    status: ObjectStatus | None = None
    proposal_number: str | None = None
    department: str | None = None
    requested_by: str | None = None
    proposal_date: str | None = None
    purpose: str | None = None
    budget_head: str | None = None
    estimated_cost: str | None = None
    proposal_status: str | None = None
    priority: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    approval_meeting_id: str | None = None
    minutes: str | None = None
    recommendations: str | None = None
    quotations: list[dict] | None = None
    comparative: list[dict] | None = None
    purchase_orders: list[dict] | None = None
    bills: list[dict] | None = None
    assets: list[dict] | None = None
    projects: list[str] | None = None
    grants: list[str] | None = None
    committees: list[str] | None = None


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
@dataclass
class VendorOutput:
    """Read-side projection of a Vendor Object (registry row/workspace)."""

    id: str
    name: str
    status: str
    version: int
    created_by: str
    created_at: str
    updated_at: str | None
    gst_number: str | None = None
    pan: str | None = None
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    bank_details: dict = field(default_factory=dict)
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    stats: dict[str, int | float] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    @staticmethod
    def from_domain(obj: UniversalObject, events: list) -> VendorOutput:
        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        return VendorOutput(
            id=str(obj.id),
            name=obj.title,
            status=obj.status.value,
            version=obj.version,
            created_by=obj.audit.created_by if obj.audit else "",
            created_at=obj.audit.created_at.isoformat() if obj.audit else "",
            updated_at=(
                obj.audit.updated_at.isoformat() if obj.audit and obj.audit.updated_at else None
            ),
            gst_number=meta.get(KEY_GST_NUMBER),
            pan=meta.get(KEY_PAN),
            contact_person=meta.get(KEY_CONTACT_PERSON),
            email=meta.get(KEY_EMAIL),
            phone=meta.get(KEY_PHONE),
            address=meta.get(KEY_ADDRESS),
            bank_details=parse_json_object(meta.get(KEY_BANK_DETAILS)),
            notes=meta.get(KEY_NOTES),
            tags=parse_json_list(meta.get(KEY_TAGS)),
            metadata=meta,
            events=[getattr(event, "name", str(event)) for event in events],
        )


@dataclass
class MeetingRefOutput:
    """Resolved approval-meeting pointer (PART 2)."""

    id: str
    title: str
    meeting_number: str | None = None
    meeting_date: str | None = None
    mode: str | None = None
    venue: str | None = None


@dataclass
class ProposalOutput:
    """Read-side projection of a Purchase Proposal Object (enriched workspace)."""

    id: str
    title: str
    status: str  # universal lifecycle
    version: int
    created_by: str
    created_at: str
    updated_at: str | None
    proposal_number: str | None = None
    department: str | None = None
    requested_by: str | None = None
    requested_name: str | None = None
    proposal_date: str | None = None
    purpose: str | None = None
    budget_head: str | None = None
    estimated_cost: float | None = None
    proposal_status: str = "draft"  # business lifecycle (metadata vocab)
    priority: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    approval_meeting_id: str | None = None
    minutes: str | None = None
    recommendations: str | None = None
    quotations: list[dict] = field(default_factory=list)
    comparative: list[dict] = field(default_factory=list)
    purchase_orders: list[dict] = field(default_factory=list)
    bills: list[dict] = field(default_factory=list)
    assets: list[dict] = field(default_factory=list)
    links: dict[str, list[dict]] = field(default_factory=dict)
    approval_meeting: MeetingRefOutput | None = None
    stats: dict[str, int | float] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    @staticmethod
    def from_domain(
        obj: UniversalObject,
        events: list,
        *,
        linked_by_id: dict[str, UniversalObject] | None = None,
    ) -> ProposalOutput:
        meta = {entry.key: entry.value for entry in obj.metadata.entries}
        return ProposalOutput(
            id=str(obj.id),
            title=obj.title,
            status=obj.status.value,
            version=obj.version,
            created_by=obj.audit.created_by if obj.audit else "",
            created_at=obj.audit.created_at.isoformat() if obj.audit else "",
            updated_at=(
                obj.audit.updated_at.isoformat() if obj.audit and obj.audit.updated_at else None
            ),
            proposal_number=meta.get(KEY_PROPOSAL_NUMBER),
            department=meta.get(KEY_DEPARTMENT),
            requested_by=meta.get(KEY_REQUESTED_BY) or None,
            requested_name=meta.get(KEY_REQUESTED_NAME) or None,
            proposal_date=meta.get(KEY_PROPOSAL_DATE),
            purpose=meta.get(KEY_PURPOSE),
            budget_head=meta.get(KEY_BUDGET_HEAD),
            estimated_cost=parse_amount(meta.get(KEY_ESTIMATED_COST)),
            proposal_status=(meta.get(KEY_PROPOSAL_STATUS) or "draft"),
            priority=meta.get(KEY_PRIORITY),
            notes=meta.get(KEY_NOTES),
            tags=parse_json_list(meta.get(KEY_TAGS)),
            approval_meeting_id=meta.get(KEY_APPROVAL_MEETING_ID) or None,
            minutes=meta.get(KEY_MINUTES),
            recommendations=meta.get(KEY_RECOMMENDATIONS),
            quotations=parse_json_object_list(meta.get(KEY_QUOTATIONS)),
            comparative=parse_json_object_list(meta.get(KEY_COMPARATIVE)),
            purchase_orders=parse_json_object_list(meta.get(KEY_PURCHASE_ORDERS)),
            bills=parse_json_object_list(meta.get(KEY_BILLS)),
            assets=parse_json_object_list(meta.get(KEY_ASSETS)),
            links=grouped_finance_links(obj, linked_by_id or {}),
            metadata=meta,
            events=[getattr(event, "name", str(event)) for event in events],
        )


# ---------------------------------------------------------------------------
# List/dashboard/budget projections
# ---------------------------------------------------------------------------
@dataclass
class ListProposalsResult:
    items: list[ProposalOutput]
    total_count: int
    page: int
    page_size: int


@dataclass
class ListVendorsResult:
    items: list[VendorOutput]
    total_count: int
    page: int
    page_size: int


@dataclass
class FinanceDashboard:
    """PART 11 dashboard cards (computed read — no stored counters)."""

    active_procurements: int
    pending_approvals: int
    total_vendors: int
    total_purchase_orders: int
    budget_utilized: float
    budget_remaining: float | None
    pending_bills: int


@dataclass
class BudgetLine:
    """PART 9 per-project tracking (composed read over frozen research helpers
    + procurement spend — never stored redundantly)."""

    project_id: str
    title: str
    approved: float | None
    released: float
    utilized: float
    remaining: float | None
    proposals: int  # proposals linked to this project
    spent: float  # procurement paid bills on those proposals


@dataclass
class AssetRegisterRow:
    """PART 8 register row: an asset section row with its proposal context."""

    proposal_id: str
    proposal_number: str | None
    proposal_title: str
    row: dict  # the whitelisted asset row (vendor_name resolved if referenced)


@dataclass
class ListBudgetsResult:
    items: list[BudgetLine]


@dataclass
class ListAssetsResult:
    items: list[AssetRegisterRow]
    total_count: int
    page: int
    page_size: int


# Re-exports used by the use cases (single-import convenience mirrors).
__all__ = [
    "format_amount",
    "link_dict",
    "linked_target_ids",
    "parse_amount",
    "parse_json_object_list",
]
