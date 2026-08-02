"""Wire <-> boundary mapping for the Finance & Procurement API.

Mirrors ``committee_mapper`` one-to-one: request dictionaries become input
DTOs and output DTOs become response dictionaries; the frozen
`uploaded_by` -> `created_by` rename happens here and only here. Link groups
ride under ``links``; the five section lists ride as top-level lists of
row dicts (whitelisted on the boundary, extra keys dropped there).
"""
from __future__ import annotations

from dataclasses import asdict

from app.application.dtos.finance import (
    FINANCE_LINK_GROUPS,
    KEY_BANK_DETAILS,
    CreateProposalInput,
    CreateVendorInput,
    ProposalOutput,
    UpdateProposalInput,
    UpdateVendorInput,
    VendorOutput,
)
from app.domain.value_objects.enums import ObjectStatus


def _str_list(value: object) -> list[str]:
    return [str(item).strip() for item in (value or []) if str(item).strip()]


def _rows(value: object) -> list[dict]:
    return [item for item in (value or []) if isinstance(item, dict)]


def _link_group(body: dict, group: str) -> list[str]:
    links = body.get("links") or {}
    return _str_list(links.get(group))


def _bank_details(value: object) -> dict:
    """Keep only the bank columns; tolerate extra keys (they are dropped)."""
    if not isinstance(value, dict):
        return {}
    return {
        key: str(value[key]).strip()
        for key in ("bank_name", "account_number", "ifsc", "branch")
        if value.get(key) not in (None, "")
    }


# ---------------------------------------------------------------------------
# Vendor inputs
# ---------------------------------------------------------------------------
def to_create_vendor_input(*, body: dict) -> CreateVendorInput:
    return CreateVendorInput(
        name=str(body.get("name") or ""),
        created_by=str(body.get("uploaded_by") or ""),
        status=ObjectStatus(body.get("status", "active")),
        gst_number=body.get("gst_number"),
        pan=body.get("pan"),
        contact_person=body.get("contact_person"),
        email=body.get("email"),
        phone=body.get("phone"),
        address=body.get("address"),
        bank_details=_bank_details(body.get(KEY_BANK_DETAILS)),
        notes=body.get("notes"),
        tags=_str_list(body.get("tags")),
    )


def to_update_vendor_input(*, body: dict) -> UpdateVendorInput:
    def present(name: str):
        return body[name] if name in body else None

    return UpdateVendorInput(
        actor=str(body.get("uploaded_by") or "system"),
        name=present("name"),
        status=ObjectStatus(body["status"]) if body.get("status") else None,
        gst_number=present("gst_number"),
        pan=present("pan"),
        contact_person=present("contact_person"),
        email=present("email"),
        phone=present("phone"),
        address=present("address"),
        bank_details=(
            _bank_details(body[KEY_BANK_DETAILS]) if KEY_BANK_DETAILS in body else None
        ),
        notes=present("notes"),
        tags=_str_list(body["tags"]) if "tags" in body else None,
    )


# ---------------------------------------------------------------------------
# Proposal inputs
# ---------------------------------------------------------------------------
def to_create_proposal_input(*, body: dict) -> CreateProposalInput:
    return CreateProposalInput(
        title=str(body.get("title") or ""),
        created_by=str(body.get("uploaded_by") or ""),
        status=ObjectStatus(body.get("status", "draft")),
        proposal_number=body.get("proposal_number"),
        department=body.get("department"),
        requested_by=body.get("requested_by"),
        proposal_date=body.get("proposal_date"),
        purpose=body.get("purpose"),
        budget_head=body.get("budget_head"),
        estimated_cost=(
            str(body.get("estimated_cost")) if body.get("estimated_cost") not in (None, "")
            else None
        ),
        proposal_status=str(body.get("proposal_status") or "draft"),
        priority=body.get("priority"),
        notes=body.get("notes"),
        tags=_str_list(body.get("tags")),
        approval_meeting_id=body.get("approval_meeting_id"),
        minutes=body.get("minutes"),
        recommendations=body.get("recommendations"),
        quotations=_rows(body.get("quotations")),
        comparative=_rows(body.get("comparative")),
        purchase_orders=_rows(body.get("purchase_orders")),
        bills=_rows(body.get("bills")),
        assets=_rows(body.get("assets")),
        projects=_link_group(body, "projects"),
        grants=_link_group(body, "grants"),
        committees=_link_group(body, "committees"),
    )


def to_update_proposal_input(*, body: dict) -> UpdateProposalInput:
    def present(name: str):
        return body[name] if name in body else None

    return UpdateProposalInput(
        actor=str(body.get("uploaded_by") or "system"),
        title=present("title"),
        status=ObjectStatus(body["status"]) if body.get("status") else None,
        proposal_number=present("proposal_number"),
        department=present("department"),
        requested_by=present("requested_by"),
        proposal_date=present("proposal_date"),
        purpose=present("purpose"),
        budget_head=present("budget_head"),
        estimated_cost=(
            str(present("estimated_cost"))
            if present("estimated_cost") not in (None, "")
            else None
        ),
        proposal_status=present("proposal_status"),
        priority=present("priority"),
        notes=present("notes"),
        tags=_str_list(body["tags"]) if "tags" in body else None,
        approval_meeting_id=present("approval_meeting_id"),
        minutes=present("minutes"),
        recommendations=present("recommendations"),
        quotations=_rows(body["quotations"]) if "quotations" in body else None,
        comparative=_rows(body["comparative"]) if "comparative" in body else None,
        purchase_orders=(
            _rows(body["purchase_orders"]) if "purchase_orders" in body else None
        ),
        bills=_rows(body["bills"]) if "bills" in body else None,
        assets=_rows(body["assets"]) if "assets" in body else None,
        projects=_link_group(body, "projects") if "links" in body else None,
        grants=_link_group(body, "grants") if "links" in body else None,
        committees=_link_group(body, "committees") if "links" in body else None,
    )


# ---------------------------------------------------------------------------
# Responses (uploaded_by renamed from created_by — frozen idiom)
# ---------------------------------------------------------------------------
def vendor_response(out: VendorOutput) -> dict:
    return {
        "id": out.id,
        "name": out.name,
        "status": out.status,
        "version": out.version,
        "uploaded_by": out.created_by,
        "created_at": out.created_at,
        "updated_at": out.updated_at,
        "gst_number": out.gst_number,
        "pan": out.pan,
        "contact_person": out.contact_person,
        "email": out.email,
        "phone": out.phone,
        "address": out.address,
        "bank_details": out.bank_details,
        "notes": out.notes,
        "tags": out.tags,
        "stats": out.stats or {"proposals": 0, "purchase_orders": 0, "pending_bills": 0, "spent": 0.0},
        "metadata": out.metadata,
        "events": out.events,
    }


def proposal_response(out: ProposalOutput) -> dict:
    return {
        "id": out.id,
        "title": out.title,
        "status": out.status,
        "version": out.version,
        "uploaded_by": out.created_by,
        "created_at": out.created_at,
        "updated_at": out.updated_at,
        "proposal_number": out.proposal_number,
        "department": out.department,
        "requested_by": out.requested_by,
        "requested_name": out.requested_name,
        "proposal_date": out.proposal_date,
        "purpose": out.purpose,
        "budget_head": out.budget_head,
        "estimated_cost": out.estimated_cost,
        "proposal_status": out.proposal_status,
        "priority": out.priority,
        "notes": out.notes,
        "tags": out.tags,
        "approval_meeting_id": out.approval_meeting_id,
        "approval_meeting": asdict(out.approval_meeting) if out.approval_meeting else None,
        "minutes": out.minutes,
        "recommendations": out.recommendations,
        "quotations": out.quotations,
        "comparative": out.comparative,
        "purchase_orders": out.purchase_orders,
        "bills": out.bills,
        "assets": out.assets,
        "links": {group: out.links.get(group, []) for group in FINANCE_LINK_GROUPS},
        "stats": out.stats
        or {
            "quotations": 0,
            "purchase_orders": 0,
            "bills": 0,
            "pending_bills": 0,
            "committed": 0.0,
            "spent": 0.0,
            "assets": 0,
        },
        "metadata": out.metadata,
        "events": out.events,
    }
