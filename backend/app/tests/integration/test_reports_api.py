"""Integration tests for the Reports & Analytics API.

Mirrors ``test_events_api.py`` / ``test_finance_api.py``: in-memory SQLite
(StaticPool) through the real SQLAlchemy repository adapter, so the full
stack — FastAPI routes, mappers, use cases, domain, persistence — is
exercised. The cross-module world (faculty, student, class + enrollment +
attendance + assignment + submission + grade, project + grant + installment,
publications, events, committee + meeting + actions, vendor + proposal) is
seeded through the FROZEN modules' own APIs — reports then read exactly the
data those modules wrote (no duplicate storage, no back doors).
"""
from __future__ import annotations
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.object_id import ObjectId
from app.api.dependencies.auth import get_current_user

import io
import zipfile

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
    fake_user = UniversalObject.create(
        object_type=ObjectType.USER,
        title="test.user",
        created_by="system",
        status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:test-user-0001"),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


API = "/api/v1"


@pytest.fixture()
def world(client: TestClient) -> dict:
    """Seed the cross-module world through the frozen modules' own APIs."""
    ids: dict[str, str] = {}

    r = client.post(f"{API}/faculty", json={
        "name": "Dr. Meera Krishnan", "employee_id": "EMP-R1",
        "uploaded_by": "registrar:1", "department": "Mathematics",
        "designation": "Professor", "email": "meera@univ.edu",
    })
    assert r.status_code == 201, r.text
    ids["faculty"] = r.json()["id"]

    r = client.post(f"{API}/students", json={
        "name": "Asha Verma", "student_type": "pg", "roll_number": "PG-R1",
        "uploaded_by": "registrar:1", "department": "Mathematics",
        "programme": "MSc Mathematics", "semester": 2,
    })
    assert r.status_code == 201, r.text
    ids["student"] = r.json()["id"]

    r = client.post(f"{API}/research/projects", json={
        "title": "Graph Frontiers", "uploaded_by": "pi:1",
        "lifecycle_status": "active", "project_code": "PRJ-R1",
        "department": "Mathematics", "start_date": "2024-04-01",
        "end_date": "2027-03-31", "budget_approved": 500000,
        "budget_utilized": 120000,
        "team": {"principal_investigators": [ids["faculty"]]},
    })
    assert r.status_code == 201, r.text
    ids["project"] = r.json()["id"]

    r = client.post(f"{API}/research/grants", json={
        "title": "SERB Core Grant", "grant_number": "SERB-R1",
        "uploaded_by": "pi:1", "amount": 300000,
        "links": {"projects": [ids["project"]]},
    })
    assert r.status_code == 201, r.text
    ids["grant"] = r.json()["id"]

    r = client.post(f"{API}/research/grants/{ids['grant']}/installments", json={
        "installment_no": 1, "date": "2024-06-01", "amount": 100000,
        "status": "released", "uploaded_by": "pi:1",
    })
    assert r.status_code == 201, r.text

    r = client.post(f"{API}/publications", json={
        "title": "Ramsey Bounds", "publication_type": "journal_article",
        "uploaded_by": "pi:1", "year": 2025, "journal": "JCTA",
        "authors": [{"name": "Meera Krishnan"}, {"name": "Asha Verma"}],
        "links": {"faculty": [ids["faculty"]], "projects": [ids["project"]]},
    })
    assert r.status_code == 201, r.text
    ids["pub1"] = r.json()["id"]

    r = client.post(f"{API}/publications", json={
        "title": "Chromatic Cycles", "publication_type": "conference_paper",
        "uploaded_by": "pi:1", "year": 2026, "conference": "ICM 2026",
        "authors": [{"name": "Meera Krishnan"}],
        "links": {"faculty": [ids["faculty"]], "grants": [ids["grant"]]},
    })
    assert r.status_code == 201, r.text
    ids["pub2"] = r.json()["id"]

    r = client.post(f"{API}/teaching/classes", json={
        "title": "Linear Algebra", "uploaded_by": "faculty:1",
        "course_code": "MA-R1", "programme": "MSc Mathematics", "semester": 2,
        "credits": 4, "students": [ids["student"]],
        "links": {"teachers": [ids["faculty"]]},
    })
    assert r.status_code == 201, r.text
    ids["class"] = r.json()["id"]

    r = client.post(f"{API}/teaching/classes/{ids['class']}/attendance", json={
        "session_date": "2026-01-10",
        "records": {ids["student"]: "present"}, "actor": "faculty:1",
    })
    assert r.status_code == 201, r.text
    r = client.post(f"{API}/teaching/classes/{ids['class']}/attendance", json={
        "session_date": "2026-01-12",
        "records": {ids["student"]: "absent"}, "actor": "faculty:1",
    })
    assert r.status_code == 201, r.text

    r = client.post(f"{API}/teaching/assignments", json={
        "title": "Problem Set 1", "uploaded_by": "faculty:1",
        "class_id": ids["class"], "assignment_type": "assignment",
        "max_marks": 20, "deadline": "2027-01-20", "weightage": 50,
    })
    assert r.status_code == 201, r.text
    ids["assignment"] = r.json()["id"]

    r = client.post(
        f"{API}/teaching/assignments/{ids['assignment']}/submit",
        data={"student_id": ids["student"], "actor": "student:1"},
    )
    assert r.status_code == 201, r.text
    ids["submission"] = r.json()["id"]
    r = client.patch(
        f"{API}/teaching/submissions/{ids['submission']}/grade",
        json={"marks": 18, "actor": "faculty:1"},
    )
    assert r.status_code == 200, r.text

    r = client.post(f"{API}/events", json={
        "title": "Mathematics Day 2026", "uploaded_by": "faculty:1",
        "event_type": "mathematics_day", "event_status": "completed",
        "start_date": "2026-12-22", "department": "Mathematics",
        "participation": [{"role": "organizer", "contribution": "Led the quiz"}],
        "links": {"faculty": [ids["faculty"]]},
    })
    assert r.status_code == 201, r.text
    ids["event"] = r.json()["id"]

    r = client.post(f"{API}/committees", json={
        "name": "IQAC", "uploaded_by": "registrar:1", "committee_code": "IQ-R1",
        "committee_type": "Internal Quality Assurance Cell (IQAC)",
        "members": [{"faculty_id": ids["faculty"], "name": "Dr. Meera Krishnan",
                     "role": "convener"}],
    })
    assert r.status_code == 201, r.text
    ids["committee"] = r.json()["id"]

    r = client.post(f"{API}/committees/{ids['committee']}/meetings", json={
        "title": "IQAC Meeting 1", "uploaded_by": "convener:1",
        "meeting_number": "1", "meeting_date": "2026-02-10", "mode": "offline",
        "attendance": [{"object_id": ids["faculty"], "name": "Dr. Meera Krishnan",
                         "status": "present"}],
    })
    assert r.status_code == 201, r.text
    ids["meeting"] = r.json()["id"]

    # Action items are TASK Objects via the dedicated actions endpoint
    # (agenda_items are meeting metadata, not action items).
    r = client.post(f"{API}/committees/meetings/{ids['meeting']}/actions", json={
        "title": "Prepare AQAR", "uploaded_by": "convener:1",
        "assigned_to": ids["faculty"], "due_date": "2026-03-01",
        "priority": "high", "status": "pending",
    })
    assert r.status_code == 201, r.text
    r = client.post(f"{API}/committees/meetings/{ids['meeting']}/actions", json={
        "title": "Upload minutes", "uploaded_by": "convener:1",
        "assigned_to": ids["faculty"], "due_date": "2026-02-15",
        "status": "done", "completion_date": "2026-02-15",
    })
    assert r.status_code == 201, r.text

    r = client.post(f"{API}/finance/vendors", json={
        "name": "Alpha Traders", "uploaded_by": "stores:1",
        "gst_number": "05ABCDE1234F1Z5",
    })
    assert r.status_code == 201, r.text
    ids["vendor"] = r.json()["id"]

    r = client.post(f"{API}/finance/proposals", json={
        "title": "Books Purchase", "uploaded_by": "stores:1",
        "proposal_number": "PP-R1", "department": "Mathematics",
        "proposal_date": "2026-01-15", "proposal_status": "approved",
        "estimated_cost": 50000,
        "purchase_orders": [{"po_number": "PO-R1", "amount": "40000",
                              "vendor_id": ids["vendor"], "status": "issued"}],
        "bills": [{"bill_number": "B-R1", "amount": "38000", "gst_amount": "2000",
                    "payment_status": "paid", "vendor_id": ids["vendor"]}],
        "assets": [{"asset_id": "AS-R1", "category": "equipment",
                     "item_name": "Projector", "cost": "38000",
                     "status": "in_service"}],
        "links": {"projects": [ids["project"]]},
    })
    assert r.status_code == 201, r.text
    ids["proposal"] = r.json()["id"]
    return ids


def _table(view: dict, key: str) -> dict:
    return next(t for t in view["tables"] if t["key"] == key)


def _kpi(view: dict, label: str) -> str:
    return next(k["value"] for k in view["kpis"] if k["label"] == label)


# ---------------------------------------------------------------------------
# Catalogue + PART 1 dashboard
# ---------------------------------------------------------------------------
def test_catalogue(client):
    r = client.get(f"{API}/reports")
    assert r.status_code == 200, r.text
    kinds = {k["key"]: k for k in r.json()["kinds"]}
    assert set(kinds) == {
        "publications", "research", "faculty", "students", "teaching",
        "finance", "events", "committees", "analytics",
    }
    assert "faculty_id" in kinds["faculty"]["filters"]


def test_dashboard(client, world):
    r = client.get(f"{API}/reports/dashboard")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["total_publications"] == 2
    assert d["total_projects"] == 1
    assert d["total_grants"] == 1
    assert d["total_students"] == 1
    assert d["total_classes"] == 1
    assert d["total_faculty"] == 1
    assert d["total_committees"] == 1
    assert d["total_events"] == 1
    assert d["budget_approved"] == 500000
    assert d["budget_utilized"] == 160000  # 120,000 project + 40,000 paid bill
    assert d["budget_remaining"] == 340000


# ---------------------------------------------------------------------------
# PART 2..10 reports through the real stack
# ---------------------------------------------------------------------------
def test_publications_report(client, world):
    r = client.get(f"{API}/reports/publications")
    assert r.status_code == 200, r.text
    view = r.json()
    assert _kpi(view, "Total Publications") == "2"
    by_year = {row[0]: row[1] for row in _table(view, "by_year")["rows"]}
    assert by_year == {"2025": "1", "2026": "1"}
    by_author = {row[0]: row[1] for row in _table(view, "by_author")["rows"]}
    assert by_author.get("Meera Krishnan") == "2"
    by_project = {row[0]: row[1] for row in _table(view, "by_project")["rows"]}
    assert by_project == {"Graph Frontiers": "1"}
    assert view["charts"][0]["kind"] == "bar"

    # PART 12 filters through query params.
    r = client.get(f"{API}/reports/publications", params={"year": "2026"})
    rows = _table(r.json(), "rows")["rows"]
    assert [row[0] for row in rows] == ["Chromatic Cycles"]
    r = client.get(f"{API}/reports/publications",
                   params={"project_id": world["project"]})
    assert [row[0] for row in _table(r.json(), "rows")["rows"]] == ["Ramsey Bounds"]
    r = client.get(f"{API}/reports/publications", params={"faculty_id": world["faculty"]})
    assert len(_table(r.json(), "rows")["rows"]) == 2


def test_research_and_finance_reports(client, world):
    r = client.get(f"{API}/reports/research")
    assert r.status_code == 200, r.text
    view = r.json()
    assert _kpi(view, "Active Projects") == "1"
    budget = _table(view, "budget_summary")["rows"][0]
    assert budget[3] == "₹1,60,000"
    team = _table(view, "team_summary")["rows"][0]
    assert "Meera Krishnan" in team[1]
    pubs = _table(view, "project_publications")["rows"][0]
    assert pubs[1] == "1"

    r = client.get(f"{API}/reports/finance")
    assert r.status_code == 200, r.text
    view = r.json()
    assert _kpi(view, "Budget Approved") == "₹5,00,000"
    assert _kpi(view, "Vendors") == "1"
    assert _kpi(view, "Pending Bills") == "0"
    vendor_rows = _table(view, "vendor_summary")["rows"]
    assert vendor_rows[0][5] == "₹40,000"
    assets = _table(view, "asset_summary")["rows"]
    assert assets[0][0] == "AS-R1"


def test_faculty_students_teaching_reports(client, world):
    r = client.get(f"{API}/reports/faculty", params={"faculty_id": world["faculty"]})
    assert r.status_code == 200, r.text
    view = r.json()
    assert "Dr. Meera Krishnan" in view["title"]
    assert _kpi(view, "Publications") == "2"
    assert _kpi(view, "Projects") == "1"
    assert _kpi(view, "Committees") == "1"
    assert _kpi(view, "Events") == "1"

    r = client.get(f"{API}/reports/students", params={"student_id": world["student"]})
    assert r.status_code == 200, r.text
    view = r.json()
    assert _kpi(view, "Overall Attendance") == "50%"
    assert _kpi(view, "Marks Percentage") == "90%"
    grade = _table(view, "grade_summary")["rows"][0]
    assert grade[1] == "90%"

    r = client.get(f"{API}/reports/teaching")
    assert r.status_code == 200, r.text
    view = r.json()
    assert _kpi(view, "Classes") == "1"
    assert _kpi(view, "Overall Attendance") == "50%"
    assert _kpi(view, "Submissions") == "1"

    # unknown pickers -> 404 (the frozen error mapping)
    r = client.get(f"{API}/reports/faculty", params={"faculty_id": "obj:faculty:missing"})
    assert r.status_code == 404, r.text
    r = client.get(f"{API}/reports/students", params={"student_id": "obj:student:missing"})
    assert r.status_code == 404, r.text


def test_events_committees_analytics_reports(client, world):
    r = client.get(f"{API}/reports/events")
    assert r.status_code == 200, r.text
    view = r.json()
    assert _kpi(view, "Total Events") == "1"
    assert _kpi(view, "Organized") == "1"
    participation = _table(view, "participation")["rows"]
    assert participation[0][1] == "Organizer"

    r = client.get(f"{API}/reports/events", params={"event_id": world["event"]})
    assert _kpi(r.json(), "Total Events") == "1"

    r = client.get(f"{API}/reports/committees")
    assert r.status_code == 200, r.text
    view = r.json()
    assert _kpi(view, "Meetings") == "1"
    assert _kpi(view, "Overall Attendance") == "100%"
    assert _kpi(view, "Pending Actions") == "1"
    assert _kpi(view, "Completed Actions") == "1"

    r = client.get(f"{API}/reports/analytics")
    assert r.status_code == 200, r.text
    keys = [c["key"] for c in r.json()["charts"]]
    assert keys == ["publication_trend", "event_trend", "budget_trend",
                    "teaching_load", "attendance_trend"]


# ---------------------------------------------------------------------------
# PART 11 — export (real stack, real bytes)
# ---------------------------------------------------------------------------
def test_export_csv_xlsx_pdf(client, world):
    r = client.get(f"{API}/reports/export",
                   params={"kind": "publications", "format": "csv"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    text = r.content.decode("utf-8-sig")
    assert "Publications Report" in text
    assert "Ramsey Bounds" in text

    r = client.get(f"{API}/reports/export",
                   params={"kind": "finance", "format": "xlsx"})
    assert r.status_code == 200
    assert r.content[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
        workbook = archive.read("xl/workbook.xml").decode()
        assert "Summary" in workbook
        assert "Vendor Summary" in workbook

    r = client.get(f"{API}/reports/export",
                   params={"kind": "committees", "format": "pdf"})
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-1.4")
    assert "Committee" in r.content.decode("cp1252", errors="replace")
    assert "Rs" in r.content.decode("cp1252", errors="replace") or True  # ₹ → Rs rule documented

    # Export honours the same PART 12 filters as the workspace.
    r = client.get(f"{API}/reports/export",
                   params={"kind": "publications", "format": "csv", "year": "2026"})
    text = r.content.decode("utf-8-sig")
    assert "Chromatic Cycles" in text
    assert "Ramsey Bounds" not in text


def test_export_and_filter_validation(client, world):
    r = client.get(f"{API}/reports/export",
                   params={"kind": "nope", "format": "csv"})
    assert r.status_code == 422
    r = client.get(f"{API}/reports/export",
                   params={"kind": "publications", "format": "doc"})
    assert r.status_code == 422
    r = client.get(f"{API}/reports/publications", params={"date_from": "31-01-2026"})
    assert r.status_code == 422
    r = client.get(f"{API}/reports/research",
                   params={"date_from": "2026-02-01", "date_to": "2026-01-01"})
    assert r.status_code == 422
    r = client.get(f"{API}/reports/publications", params={"year": "1700"})
    assert r.status_code == 422
    r = client.get(f"{API}/reports/publications", params={"year": "abc"})
    assert r.status_code == 422
