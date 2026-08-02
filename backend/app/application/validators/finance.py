"""Validators for the Finance & Procurement inputs.

Mirrors ``validators/committee.py`` one-to-one: file-local regexes, small
``assert_*`` helpers raising ``ValidationError`` (mapped to 422 by the
routers), and per-input entry points called first thing in every use case.
"""
from __future__ import annotations

import re

from app.application.dtos.finance import (
    ASSET_CATEGORIES,
    ASSET_ROW_KEYS,
    ASSET_STATUSES,
    BILL_ROW_KEYS,
    COMPARATIVE_ROW_KEYS,
    COMPLIANCE_VALUES,
    PAYMENT_STATUSES,
    PO_STATUSES,
    PROPOSAL_PRIORITIES,
    PROPOSAL_STATUSES,
    PURCHASE_ORDER_ROW_KEYS,
    QUOTATION_ROW_KEYS,
    CreateProposalInput,
    CreateVendorInput,
    UpdateProposalInput,
    UpdateVendorInput,
)
from app.application.exceptions import ValidationError

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_GST_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")
_AMOUNT_RE = re.compile(r"^-?\d+(\.\d{1,2})?$")


def _err(message: str) -> None:
    raise ValidationError(message)


def assert_optional_date(value: str | None, field: str) -> None:
    if value not in (None, "") and not _DATE_RE.match(str(value).strip()):
        _err(f"{field} must be an ISO date (YYYY-MM-DD).")


def assert_optional_amount(value, field: str, *, allow_blank: bool = True) -> None:
    if value in (None, ""):
        if not allow_blank:
            _err(f"{field} is required.")
        return
    if not _AMOUNT_RE.match(str(value).strip()):
        _err(f"{field} must be a non-negative decimal amount.")
    if str(value).strip().startswith("-"):
        _err(f"{field} must be a non-negative decimal amount.")


def assert_optional_email(value: str | None, field: str = "email") -> None:
    if value not in (None, "") and not _EMAIL_RE.match(str(value).strip()):
        _err(f"{field} must be a valid email address.")


def assert_optional_gst(value: str | None) -> None:
    if value not in (None, "") and not _GST_RE.match(str(value).strip().upper()):
        _err("gst_number must be a valid 15-character GSTIN (e.g. 07AABCS1429B1Z5).")


def assert_optional_pan(value: str | None) -> None:
    if value not in (None, "") and not _PAN_RE.match(str(value).strip().upper()):
        _err("pan must be a valid PAN (e.g. AABCS1429B).")


def assert_choice(value: str | None, choices: tuple[str, ...], field: str) -> None:
    if value not in (None, "") and str(value).strip() not in choices:
        _err(f"{field} must be one of: {', '.join(choices)}.")


def _assert_str_keys(row: dict, whitelist: tuple[str, ...], section: str, index: int) -> None:
    if not isinstance(row, dict):
        _err(f"{section} row {index} must be an object.")
        return
    unknown = [key for key in row if key not in whitelist]
    if unknown:
        _err(f"{section} row {index} carries unknown keys: {', '.join(sorted(unknown))}.")


def _assert_document_ids(row: dict, section: str, index: int) -> None:
    document_ids = row.get("document_ids")
    if document_ids is None:
        return
    if not isinstance(document_ids, list) or not all(
        isinstance(item, str) for item in document_ids
    ):
        _err(f"{section} row {index} document_ids must be a list of object ids.")


def assert_valid_quotations(rows: list[dict]) -> None:
    for index, row in enumerate(rows, start=1):
        _assert_str_keys(row, QUOTATION_ROW_KEYS, "quotations", index)
        if row.get("vendor_id") in (None, ""):
            _err(f"quotations row {index} requires a vendor.")
        assert_optional_date(row.get("quotation_date"), f"quotations row {index} quotation_date")
        assert_optional_date(row.get("validity_date"), f"quotations row {index} validity_date")
        assert_optional_amount(
            row.get("amount"), f"quotations row {index} amount", allow_blank=False
        )
        _assert_document_ids(row, "quotations", index)


def assert_valid_comparative(rows: list[dict]) -> None:
    recommended = 0
    for index, row in enumerate(rows, start=1):
        _assert_str_keys(row, COMPARATIVE_ROW_KEYS, "comparative", index)
        if row.get("vendor_id") in (None, ""):
            _err(f"comparative row {index} requires a vendor.")
        assert_optional_amount(
            row.get("amount"), f"comparative row {index} amount", allow_blank=False
        )
        assert_choice(
            row.get("technical_compliance"), COMPLIANCE_VALUES,
            f"comparative row {index} technical_compliance",
        )
        assert_choice(
            row.get("financial_compliance"), COMPLIANCE_VALUES,
            f"comparative row {index} financial_compliance",
        )
        flag = row.get("recommended")
        if flag not in (None, "", False, "no", "false"):
            recommended += 1
    if recommended > 1:
        _err("comparative: only one vendor may be recommended.")


def assert_valid_purchase_orders(rows: list[dict]) -> None:
    numbers: set[str] = set()
    for index, row in enumerate(rows, start=1):
        _assert_str_keys(row, PURCHASE_ORDER_ROW_KEYS, "purchase_orders", index)
        number = (row.get("po_number") or "").strip()
        if not number:
            _err(f"purchase_orders row {index} requires a po_number.")
        if number.casefold() in numbers:
            _err(f"duplicate po_number {number!r} within the proposal.")
        numbers.add(number.casefold())
        if row.get("vendor_id") in (None, ""):
            _err(f"purchase_orders row {index} requires a vendor.")
        assert_optional_date(row.get("po_date"), f"purchase_orders row {index} po_date")
        assert_optional_date(row.get("delivery_date"), f"purchase_orders row {index} delivery_date")
        assert_optional_amount(
            row.get("amount"), f"purchase_orders row {index} amount", allow_blank=False
        )
        assert_choice(row.get("status"), PO_STATUSES, f"purchase_orders row {index} status")
        _assert_document_ids(row, "purchase_orders", index)


def assert_valid_bills(rows: list[dict]) -> None:
    numbers: set[str] = set()
    for index, row in enumerate(rows, start=1):
        _assert_str_keys(row, BILL_ROW_KEYS, "bills", index)
        number = (row.get("bill_number") or "").strip()
        if not number:
            _err(f"bills row {index} requires a bill_number.")
        if number.casefold() in numbers:
            _err(f"duplicate bill_number {number!r} within the proposal.")
        numbers.add(number.casefold())
        if row.get("vendor_id") in (None, ""):
            _err(f"bills row {index} requires a vendor.")
        assert_optional_date(row.get("bill_date"), f"bills row {index} bill_date")
        assert_optional_date(row.get("paid_date"), f"bills row {index} paid_date")
        assert_optional_amount(row.get("amount"), f"bills row {index} amount", allow_blank=False)
        assert_optional_amount(row.get("gst_amount"), f"bills row {index} gst_amount")
        assert_choice(
            row.get("payment_status"), PAYMENT_STATUSES, f"bills row {index} payment_status"
        )
        _assert_document_ids(row, "bills", index)


def assert_valid_assets(rows: list[dict]) -> None:
    identifiers: set[str] = set()
    for index, row in enumerate(rows, start=1):
        _assert_str_keys(row, ASSET_ROW_KEYS, "assets", index)
        identifier = (row.get("asset_id") or "").strip()
        if not identifier:
            _err(f"assets row {index} requires an asset_id.")
        if identifier.casefold() in identifiers:
            _err(f"duplicate asset_id {identifier!r} within the proposal.")
        identifiers.add(identifier.casefold())
        if row.get("item_name") in (None, ""):
            _err(f"assets row {index} requires an item_name.")
        assert_choice(row.get("category"), ASSET_CATEGORIES, f"assets row {index} category")
        assert_choice(row.get("status"), ASSET_STATUSES, f"assets row {index} status")
        assert_optional_date(row.get("purchase_date"), f"assets row {index} purchase_date")
        assert_optional_date(row.get("warranty_expiry"), f"assets row {index} warranty_expiry")
        assert_optional_amount(row.get("cost"), f"assets row {index} cost")


def assert_valid_bank_details(details: dict) -> None:
    if details is None:
        return
    if not isinstance(details, dict):
        _err("bank_details must be an object (bank_name/account_number/ifsc/branch).")
    unknown = [key for key in details if key not in ("bank_name", "account_number", "ifsc", "branch")]
    if unknown:
        _err(f"bank_details carries unknown keys: {', '.join(sorted(unknown))}.")


def _assert_proposal_sections(data) -> None:
    assert_valid_quotations(list(data.quotations or []))
    assert_valid_comparative(list(data.comparative or []))
    assert_valid_purchase_orders(list(data.purchase_orders or []))
    assert_valid_bills(list(data.bills or []))
    assert_valid_assets(list(data.assets or []))


def _assert_proposal_core(
    *,
    proposal_date,
    estimated_cost,
    proposal_status,
    priority,
) -> None:
    assert_optional_date(proposal_date, "proposal_date")
    assert_optional_amount(estimated_cost, "estimated_cost")
    assert_choice(proposal_status, PROPOSAL_STATUSES, "proposal_status")
    assert_choice(priority, PROPOSAL_PRIORITIES, "priority")


def assert_valid_create_proposal_input(data: CreateProposalInput) -> None:
    if data.title in (None, "") or not str(data.title).strip():
        _err("title is required.")
    if data.created_by in (None, "") or not str(data.created_by).strip():
        _err("created_by is required.")
    _assert_proposal_core(
        proposal_date=data.proposal_date,
        estimated_cost=data.estimated_cost,
        proposal_status=data.proposal_status,
        priority=data.priority,
    )
    if data.tags is not None and not all(isinstance(tag, str) for tag in data.tags):
        _err("tags must be a list of strings.")
    _assert_proposal_sections(data)


def assert_valid_update_proposal_input(data: UpdateProposalInput) -> None:
    if data.title is not None and not str(data.title).strip():
        _err("title cannot be blank.")
    if not str(data.actor or "").strip():
        _err("actor must not be empty (audit trail).")
    _assert_proposal_core(
        proposal_date=data.proposal_date,
        estimated_cost=data.estimated_cost,
        proposal_status=data.proposal_status,
        priority=data.priority,
    )
    if data.tags is not None and not all(isinstance(tag, str) for tag in data.tags):
        _err("tags must be a list of strings.")
    if data.quotations is not None:
        assert_valid_quotations(list(data.quotations))
    if data.comparative is not None:
        assert_valid_comparative(list(data.comparative))
    if data.purchase_orders is not None:
        assert_valid_purchase_orders(list(data.purchase_orders))
    if data.bills is not None:
        assert_valid_bills(list(data.bills))
    if data.assets is not None:
        assert_valid_assets(list(data.assets))


def assert_valid_create_vendor_input(data: CreateVendorInput) -> None:
    if data.name in (None, "") or not str(data.name).strip():
        _err("name is required.")
    if data.created_by in (None, "") or not str(data.created_by).strip():
        _err("created_by is required.")
    assert_optional_gst(data.gst_number)
    assert_optional_pan(data.pan)
    assert_optional_email(data.email)
    assert_valid_bank_details(data.bank_details)
    if data.tags is not None and not all(isinstance(tag, str) for tag in data.tags):
        _err("tags must be a list of strings.")


def assert_valid_update_vendor_input(data: UpdateVendorInput) -> None:
    if data.name is not None and not str(data.name).strip():
        _err("name cannot be blank.")
    if not str(data.actor or "").strip():
        _err("actor must not be empty (audit trail).")
    assert_optional_gst(data.gst_number)
    assert_optional_pan(data.pan)
    assert_optional_email(data.email)
    assert_valid_bank_details(data.bank_details)
    if data.tags is not None and not all(isinstance(tag, str) for tag in data.tags):
        _err("tags must be a list of strings.")


def assert_valid_list_query(page: int, page_size: int) -> None:
    if page < 1:
        _err("page must be >= 1.")
    if page_size < 1 or page_size > 100:
        _err("page_size must be between 1 and 100.")


_FINANCIAL_YEAR_RE = re.compile(r"^\d{4}-\d{2}$")


def assert_optional_financial_year(value: str | None) -> None:
    if value in (None, ""):
        return
    if not _FINANCIAL_YEAR_RE.match(str(value).strip()):
        _err("financial_year must look like 2026-27 (April-March).")
    start = int(str(value).strip()[:4])
    end = int(str(value).strip()[5:])
    if end != (start + 1) % 100:
        _err("financial_year must be consecutive years (e.g. 2026-27).")
