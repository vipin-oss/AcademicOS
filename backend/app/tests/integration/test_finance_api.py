"""Integration tests for the Finance & Procurement API (procurement slice).

Mirrors ``test_committees_api.py`` / ``test_faculty_api.py``: in-memory
SQLite (StaticPool) through the real SQLAlchemy repository adapter, so the
full stack — FastAPI routes, mappers, use cases, domain, persistence — is
exercised without PostgreSQL, disk state, or network. Linked Objects
(faculty, projects, grants, committees, meetings, documents) are built
through the FROZEN modules' own APIs.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic_settings")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.session import get_db
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()

    def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


API = "/api/v1"


def _vendor(client, name="Acme Scientific Supplies", gst="07AABCS1429B1Z5", **overrides):
    body = {
        "name": name,
        "uploaded_by": "finance:1",
        "status": "active",
        "gst_number": gst,
        "pan": "AABCS1429B",
        "contact_person": "Ravi Kumar",
        "email": "sales@acme.example",
        "phone": "9810012345",
        "address": "Okhla, New Delhi",
        "bank_details": {
            "bank_name": "SBI",
            "account_number": "12345678901",
            "ifsc": "SBIN0001234",
            "branch": "Okhla",
        },
        "tags": ["lab"],
    }
    body.update(overrides)
    return client.post(f"{API}/finance/vendors", json=body)


def _proposal(client, vendor_id: str, **overrides):
    body = {
        "title": "HPC Nodes Purchase",
        "uploaded_by": "finance:1",
        "status": "draft",
        "proposal_number": "PP-2026-001",
        "department": "Physics",
        "proposal_date": "2026-07-15",
        "purpose": "Compute expansion",
        "budget_head": "Capital",
        "estimated_cost": "450000",
        "proposal_status": "submitted",
        "priority": "high",
        "tags": ["it"],
        "quotations": [
            {
                "vendor_id": vendor_id,
                "quotation_date": "2026-07-10",
                "amount": "440000",
                "validity_date": "2026-09-30",
            }
        ],
        "comparative": [
            {
                "vendor_id": vendor_id,
                "amount": "440000",
                "technical_compliance": "compliant",
                "financial_compliance": "compliant",
                "recommended": True,
            }
        ],
        "purchase_orders": [
            {
                "po_number": "PO-1",
                "po_date": "2026-07-20",
                "vendor_id": vendor_id,
                "amount": "440000",
                "status": "issued",
                "delivery_date": "2026-08-30",
            }
        ],
        "bills": [
            {
                "bill_number": "B-1",
                "invoice_number": "INV-1",
                "vendor_id": vendor_id,
                "bill_date": "2026-08-01",
                "amount": "440000",
                "gst_amount": "79200",
                "payment_status": "paid",
                "paid_date": "2026-08-02",
                "po_number": "PO-1",
            }
        ],
        "assets": [
            {
                "asset_id": "AST-1",
                "category": "computer",
                "item_name": "HPC Node",
                "serial_number": "SN123",
                "location": "Server Room",
                "purchase_date": "2026-08-01",
                "cost": "440000",
                "status": "in_service",
                "po_number": "PO-1",
            }
        ],
    }
    body.update(overrides)
    return client.post(f"{API}/finance/proposals", json=body)


# ---------------------------------------------------------------------------
# Vendor registry (PART 3)
# ---------------------------------------------------------------------------
def test_vendor_crud_with_duplicates_and_validation(client):
    created = _vendor(client)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["bank_details"]["ifsc"] == "SBIN0001234"
    assert body["gst_number"] == "07AABCS1429B1Z5"
    vendor_id = body["id"]

    duplicate_gst = _vendor(client, name="Other Co", pan=None)
    assert duplicate_gst.status_code == 409
    duplicate_name = _vendor(client, gst=None, pan=None)
    assert duplicate_name.status_code == 409

    bad_gst = _vendor(client, name="Zed Traders", gst="nope", pan=None)
    assert bad_gst.status_code == 422
    bad_email = _vendor(client, name="Zed Traders", gst=None, pan=None, email="nope")
    assert bad_email.status_code == 422

    listed = client.get(f"{API}/finance/vendors", params={"q": "acme 07aabcs"}).json()
    assert listed["total_count"] == 1
    assert listed["items"][0]["id"] == vendor_id

    merged = client.put(
        f"{API}/finance/vendors/{vendor_id}",
        json={"phone": "9000000000", "uploaded_by": "finance:2"},
    )
    assert merged.status_code == 200
    assert merged.json()["phone"] == "9000000000"
    assert merged.json()["gst_number"] == "07AABCS1429B1Z5"  # untouched

    assert client.get(f"{API}/finance/vendors/obj:vendor:NOPE").status_code == 404
    assert client.delete(f"{API}/finance/vendors/{vendor_id}").status_code == 204
    assert client.get(f"{API}/finance/vendors/{vendor_id}").status_code == 404


# ---------------------------------------------------------------------------
# Proposal create + the 409/422 registry guards (PARTS 1/7)
# ---------------------------------------------------------------------------
def test_proposal_create_duplicate_and_reference_guards(client):
    vendor = _vendor(client).json()
    created = _proposal(client, vendor["id"])
    assert created.status_code == 201, created.text

    duplicate_number = _proposal(client, vendor["id"], title="Another")
    assert duplicate_number.status_code == 409
    duplicate_triple = _proposal(client, vendor["id"], proposal_number=None)
    assert duplicate_triple.status_code == 409

    faculty = client.post(
        f"{API}/faculty",
        json={"name": "Dr. Rao", "employee_id": "F-1", "uploaded_by": "registrar:1"},
    ).json()
    bad_section_vendor = _proposal(
        client, vendor["id"], title="Bad Ref", proposal_number="PP-X1",
        quotations=[{"vendor_id": faculty["id"], "amount": "5"}],
    )
    assert bad_section_vendor.status_code == 422
    bad_requester = _proposal(client, vendor["id"], title="Bad Req", proposal_number="PP-X2", requested_by=vendor["id"])
    assert bad_requester.status_code == 422
    bad_link = _proposal(client, vendor["id"], title="Bad Link", proposal_number="PP-X3", links={"projects": [vendor["id"]]})
    assert bad_link.status_code == 422
    bad_amount = _proposal(
        client, vendor["id"], title="Bad Amount", proposal_number="PP-X4",
        quotations=[{"vendor_id": vendor["id"], "amount": "lots"}],
    )
    assert bad_amount.status_code == 422
    bad_fy = client.get(f"{API}/finance/proposals", params={"financial_year": "2026-26"})
    assert bad_fy.status_code == 422


# ---------------------------------------------------------------------------
# PART 2 + PART 6 — committee linkage and document resolution
# ---------------------------------------------------------------------------
def test_proposal_committee_meeting_and_document_links(client):
    vendor = _vendor(client).json()
    committee = client.post(
        f"{API}/committees",
        json={
            "name": "Purchase Committee", "uploaded_by": "registrar:1",
            "committee_code": "PC-01", "committee_type": "Purchase Committee",
            "status": "active",
        },
    ).json()
    meeting = client.post(
        f"{API}/committees/{committee['id']}/meetings",
        json={"title": "7th Purchase Meeting", "uploaded_by": "registrar:1",
              "meeting_number": "7", "meeting_date": "2026-07-28", "mode": "hybrid"},
    ).json()
    # Frozen Documents module: an uploaded quotation file.
    import io

    document = client.post(
        f"{API}/documents",
        files={"file": ("quote.pdf", io.BytesIO(b"%PDF-1.4 quote"), "application/pdf")},
        data={"title": "Quote A.pdf", "document_type": "pdf",
              "uploaded_by": "finance:1", "object_id": vendor["id"]},
    ).json()
    assert "id" in document, document

    # quotations carries the supporting document
    created = client.post(
        f"{API}/finance/proposals",
        json={
            "title": "HPC Nodes Purchase",
            "uploaded_by": "finance:1",
            "proposal_number": "PP-2026-777",
            "proposal_date": "2026-07-15",
            "approval_meeting_id": meeting["id"],
            "minutes": "Committee approved the L1 vendor.",
            "recommendations": "Award to Acme.",
            "quotations": [
                {"vendor_id": vendor["id"], "amount": "440000",
                 "document_ids": [document["id"]]}
            ],
            "links": {"committees": [committee["id"]]},
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["approval_meeting"]["meeting_number"] == "7"
    assert body["approval_meeting"]["mode"] == "hybrid"
    assert body["quotations"][0]["supporting_documents"] == [
        {"id": document["id"], "title": "Quote A.pdf"}
    ]
    assert body["links"]["committees"][0]["title"] == "Purchase Committee"

    fetched = client.get(f"{API}/finance/proposals/{body['id']}").json()
    assert fetched["minutes"] == "Committee approved the L1 vendor."
    assert fetched["recommendations"] == "Award to Acme."

    # List rows carry the same denormalised shape as the workspace payload
    # (the shared enrichment — resolved approval meeting included).
    listed = client.get(f"{API}/finance/proposals").json()
    row = next(item for item in listed["items"] if item["id"] == body["id"])
    assert row["approval_meeting"]["id"] == meeting["id"]
    assert row["approval_meeting"]["meeting_number"] == "7"

    bad_meeting = client.post(
        f"{API}/finance/proposals",
        json={"title": "Bad Meeting", "uploaded_by": "finance:1",
              "approval_meeting_id": vendor["id"]},
    )
    assert bad_meeting.status_code == 422


# ---------------------------------------------------------------------------
# The cross-module money test (PARTS 8/9/11 + documents integration)
# ---------------------------------------------------------------------------
def test_full_procurement_cycle_and_dashboard_budget_lens(client):
    vendor = _vendor(client).json()
    faculty = client.post(
        f"{API}/faculty",
        json={"name": "Dr. Nandini Rao", "employee_id": "F-9", "uploaded_by": "registrar:1"},
    ).json()
    project = client.post(
        f"{API}/research/projects",
        json={"title": "Quantum Sensors", "uploaded_by": "registrar:1",
              "lifecycle_status": "active", "budget_approved": "1000000"},
    ).json()
    grant = client.post(
        f"{API}/research/grants",
        json={"title": "SERB Core Grant", "grant_number": "SERB-1", "uploaded_by": "registrar:1",
              "amount": 800000, "links": {"projects": [project["id"]], "funding_agencies": []}},
    ).json()

    created = _proposal(
        client,
        vendor["id"],
        requested_by=faculty["id"],
        links={"projects": [project["id"]], "grants": [grant["id"]], "committees": []},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["requested_name"] == "Dr. Nandini Rao"
    assert body["quotations"][0]["vendor_name"] == "Acme Scientific Supplies"
    assert body["purchase_orders"][0]["vendor_name"] == "Acme Scientific Supplies"
    assert body["stats"]["spent"] == 519200.0  # 440000 + 79200 GST (paid)
    assert body["links"]["projects"][0]["id"] == project["id"]

    dashboard = client.get(f"{API}/finance/dashboard").json()
    assert dashboard["active_procurements"] == 1
    assert dashboard["pending_approvals"] == 1
    assert dashboard["total_vendors"] == 1
    assert dashboard["total_purchase_orders"] == 1
    assert dashboard["budget_utilized"] == 519200.0
    assert dashboard["budget_remaining"] == 480800.0
    assert dashboard["pending_bills"] == 0

    lines = client.get(f"{API}/finance/budgets").json()["items"]
    assert len(lines) == 1
    line = lines[0]
    assert line["project_id"] == project["id"]
    assert line["approved"] == 1000000.0
    assert line["utilized"] == 519200.0
    assert line["spent"] == 519200.0
    assert line["proposals"] == 1

    register = client.get(f"{API}/finance/assets").json()
    assert register["total_count"] == 1
    assert register["items"][0]["row"]["item_name"] == "HPC Node"
    assert register["items"][0]["proposal_number"] == "PP-2026-001"

    vendor_view = client.get(f"{API}/finance/vendors/{vendor['id']}").json()
    assert vendor_view["stats"]["proposals"] == 1
    assert vendor_view["stats"]["purchase_orders"] == 1
    assert vendor_view["stats"]["spent"] == 519200.0


# ---------------------------------------------------------------------------
# PART 12 search & filters
# ---------------------------------------------------------------------------
def test_proposal_search_filters_and_financial_year(client):
    vendor = _vendor(client).json()
    assert _proposal(client, vendor["id"]).status_code == 201
    assert _proposal(
        client, vendor["id"], title="Library Furniture Purchase",
        proposal_number="PP-2026-002", department="Library", proposal_date="2026-02-10",
        proposal_status="approved",
        quotations=[{"vendor_id": vendor["id"], "amount": "125000"}],
        comparative=[], purchase_orders=[], bills=[], assets=[],
    ).status_code == 201

    by_q = client.get(f"{API}/finance/proposals", params={"q": "hpc physics"}).json()
    assert by_q["total_count"] == 1
    by_vendor = client.get(f"{API}/finance/proposals", params={"vendor": "acme"}).json()
    assert by_vendor["total_count"] == 2
    by_dept = client.get(f"{API}/finance/proposals", params={"department": "libr"}).json()
    assert by_dept["total_count"] == 1
    by_fy = client.get(f"{API}/finance/proposals", params={"financial_year": "2025-26"}).json()
    assert by_fy["total_count"] == 1 and by_fy["items"][0]["title"] == "Library Furniture Purchase"
    by_fy_miss = client.get(f"{API}/finance/proposals", params={"financial_year": "2024-25"}).json()
    assert by_fy_miss["total_count"] == 0
    by_status = client.get(f"{API}/finance/proposals", params={"status": "approved"}).json()
    assert by_status["total_count"] == 1
    page_two = client.get(
        f"{API}/finance/proposals", params={"page": 2, "page_size": 1}
    ).json()
    assert page_two["total_count"] == 2 and len(page_two["items"]) == 1


# ---------------------------------------------------------------------------
# Update merge contract + 404s + delete
# ---------------------------------------------------------------------------
def test_proposal_update_merge_section_replace_and_delete(client):
    vendor = _vendor(client).json()
    proposal = _proposal(client, vendor["id"]).json()
    url = f"{API}/finance/proposals/{proposal['id']}"

    merged = client.put(url, json={"proposal_status": "approved", "uploaded_by": "finance:2"})
    assert merged.status_code == 200
    body = merged.json()
    assert body["proposal_status"] == "approved"
    assert body["quotations"][0]["vendor_name"] == "Acme Scientific Supplies"
    assert body["stats"]["spent"] == 519200.0

    replaced = client.put(
        url,
        json={
            "quotations": [
                {"vendor_id": vendor["id"], "amount": "445000", "remarks": "Revised"}
            ],
            "uploaded_by": "finance:2",
        },
    )
    assert replaced.status_code == 200
    assert len(replaced.json()["quotations"]) == 1
    assert replaced.json()["quotations"][0]["remarks"] == "Revised"

    patched = client.patch(url, json={"priority": "medium", "uploaded_by": "finance:2"})
    assert patched.status_code == 200 and patched.json()["priority"] == "medium"

    assert client.put(
        f"{API}/finance/proposals/obj:purchase:NOPE", json={"notes": "x"}
    ).status_code == 404
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404
    # Vendor survives the proposal delete (institutional record elsewhere).
    assert client.get(f"{API}/finance/vendors/{vendor['id']}").status_code == 200


# ---------------------------------------------------------------------------
# Section validators over the wire (PARTS 4/5/6/7/8 shapes)
# ---------------------------------------------------------------------------
def test_section_wire_validation_errors(client):
    vendor = _vendor(client).json()
    two_recommended = _proposal(
        client, vendor["id"], title="Two Rec", comparative=[
            {"vendor_id": vendor["id"], "amount": "1", "recommended": True},
            {"vendor_id": vendor["id"], "amount": "2", "recommended": True},
        ],
    )
    assert two_recommended.status_code == 422
    dup_po = _proposal(
        client, vendor["id"], title="Dup PO", purchase_orders=[
            {"po_number": "PO-1", "vendor_id": vendor["id"], "amount": "10"},
            {"po_number": "PO-1", "vendor_id": vendor["id"], "amount": "20"},
        ],
    )
    assert dup_po.status_code == 422
    unknown_key = _proposal(
        client, vendor["id"], title="Bad Key",
        quotations=[{"vendor_id": vendor["id"], "amount": "5", "bogus": "x"}],
    )
    assert unknown_key.status_code == 422
    bad_asset = _proposal(
        client, vendor["id"], title="Bad Asset",
        assets=[{"asset_id": "A-1", "category": "spaceship", "item_name": "X"}],
    )
    assert bad_asset.status_code == 422
    bad_status = _proposal(client, vendor["id"], title="Bad Status", proposal_status="limbo")
    assert bad_status.status_code == 422


# ---------------------------------------------------------------------------
# Events + audit stays wired (frozen Object semantics)
# ---------------------------------------------------------------------------
def test_proposal_events_and_audit_projection(client):
    vendor = _vendor(client).json()
    created = _proposal(client, vendor["id"]).json()
    assert any("Created" in event for event in created["events"])
    assert created["uploaded_by"] == "finance:1"
    assert created["metadata"]["proposal_number"] == "PP-2026-001"
    assert created["version"] >= 1
    updated = client.put(
        f"{API}/finance/proposals/{created['id']}",
        json={"notes": "Audit note", "uploaded_by": "finance:2"},
    ).json()
    assert updated["notes"] == "Audit note"
    assert any("Updated" in event or "Metadata" in event for event in updated["events"])
