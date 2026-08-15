"""Integration tests for the Productivity Hub API (real stack, in-memory).

Mirrors ``test_reports_api.py``: StaticPool in-memory SQLite + FastAPI
TestClient; the cross-module world is seeded through the FROZEN modules'
own APIs, and the productivity aggregation plus its own write paths are
asserted end-to-end. All dates are relative to the real today so the suite
is deterministic on any day.
"""
from __future__ import annotations
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.object_id import ObjectId
from app.api.dependencies.auth import get_current_user

import datetime as dt

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.infrastructure.db.models.object_model import Base  # noqa: E402
from app.infrastructure.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


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
_TODAY = dt.date.today()


def d(offset: int) -> str:
    return (_TODAY + dt.timedelta(days=offset)).isoformat()


TODAY = d(0)
WEEKDAY_TODAY = _TODAY.strftime("%a").lower()  # frozen abbreviation: "mon" ..


@pytest.fixture()
def world(client: TestClient) -> dict:
    """Seed the cross-module world through the frozen modules' own APIs."""
    ids: dict[str, str] = {}

    r = client.post(f"{API}/committees", json={
        "name": "IQAC Productivity", "uploaded_by": "test", "committee_code": "PC-1",
        "committee_type": "Internal Quality Assurance Cell (IQAC)",
    })
    assert r.status_code == 201, r.text
    ids["committee"] = r.json()["id"]

    r = client.post(f"{API}/committees/{ids['committee']}/meetings", json={
        "title": "IQAC Plan Meet", "uploaded_by": "test", "meeting_number": "1",
        "meeting_date": TODAY, "mode": "offline",
    })
    assert r.status_code == 201, r.text
    ids["meeting"] = r.json()["id"]

    r = client.post(f"{API}/committees/meetings/{ids['meeting']}/actions", json={
        "title": "Prepare AQAR annexure", "status": "pending", "due_date": d(-2),
        "priority": "high", "uploaded_by": "test",
    })
    assert r.status_code == 201, r.text
    ids["action"] = r.json()["id"]

    r = client.post(f"{API}/events", json={
        "title": "Mathematics Day", "uploaded_by": "test", "event_type": "mathematics_day",
        "start_date": TODAY, "end_date": TODAY, "event_status": "planned",
    })
    assert r.status_code == 201, r.text
    ids["event"] = r.json()["id"]

    r = client.post(f"{API}/research/projects", json={
        "title": "Graph Frontiers", "uploaded_by": "test", "lifecycle_status": "active",
        "project_code": "PR-1", "start_date": TODAY, "end_date": d(20),
    })
    assert r.status_code == 201, r.text
    ids["project"] = r.json()["id"]

    r = client.post(f"{API}/research/projects/{ids['project']}/milestones", json={
        "title": "Interim report", "date": d(1), "status": "pending",
    })
    assert r.status_code == 201, r.text
    ids["milestone"] = r.json()["id"]

    r = client.post(f"{API}/research/grants", json={
        "title": "SERB Core", "grant_number": "SG-1", "uploaded_by": "test",
        "amount": 300000, "links": {"projects": [ids["project"]]},
    })
    assert r.status_code == 201, r.text
    ids["grant"] = r.json()["id"]

    r = client.post(f"{API}/research/grants/{ids['grant']}/installments", json={
        "installment_no": 1, "date": d(2), "amount": 100000, "status": "scheduled",
    })
    assert r.status_code == 201, r.text

    r = client.post(f"{API}/students", json={
        "name": "Asha Verma", "student_type": "pg", "roll_number": "PG-P1",
        "uploaded_by": "test", "department": "Mathematics",
        "programme": "MSc Mathematics", "semester": 2,
    })
    assert r.status_code == 201, r.text
    ids["student"] = r.json()["id"]

    r = client.post(f"{API}/teaching/classes", json={
        "title": "Linear Algebra", "uploaded_by": "test", "course_code": "MA-P1",
        "students": [ids["student"]],
        "weekly_schedule": [{"day": WEEKDAY_TODAY, "start": "09:00", "end": "10:00"}],
    })
    assert r.status_code == 201, r.text
    ids["class"] = r.json()["id"]

    r = client.post(f"{API}/teaching/assignments", json={
        "title": "Problem Set 4", "uploaded_by": "test", "class_id": ids["class"],
        "assignment_type": "assignment", "max_marks": 20, "deadline": d(1), "weightage": 50,
    })
    assert r.status_code == 201, r.text
    ids["assignment"] = r.json()["id"]

    r = client.post(f"{API}/teaching/classes/{ids['class']}/attendance", json={
        "session_date": TODAY, "records": {ids["student"]: "present"}, "actor": "test",
    })
    assert r.status_code == 201, r.text

    r = client.post(f"{API}/finance/vendors", json={
        "name": "Alpha Traders", "uploaded_by": "test",
    })
    assert r.status_code == 201, r.text
    ids["vendor"] = r.json()["id"]

    r = client.post(f"{API}/finance/proposals", json={
        "title": "Books Purchase", "uploaded_by": "test", "proposal_number": "PP-1",
        "proposal_date": d(-5), "proposal_status": "approved", "estimated_cost": 50000,
        "purchase_orders": [{"po_number": "PO-9", "amount": "40000",
                             "vendor_id": ids["vendor"], "status": "issued",
                             "delivery_date": d(1)}],
        "bills": [{"bill_number": "B-3", "amount": "38000", "gst_amount": "2000",
                   "payment_status": "pending", "vendor_id": ids["vendor"],
                   "bill_date": d(-1)}],
    })
    assert r.status_code == 201, r.text
    ids["proposal"] = r.json()["id"]
    return ids


def test_calendar_feed_aggregates_every_source(client: TestClient, world: dict):
    r = client.get(f"{API}/productivity/calendar", params={
        "date_from": d(-2), "date_to": d(7),
    })
    assert r.status_code == 200, r.text
    feed = r.json()
    by_source: dict[str, list] = {}
    for item in feed["items"]:
        by_source.setdefault(item["source"], []).append(item)

    assert any(i["title"] == "Mathematics Day" for i in by_source["events"])
    meet = next(i for i in by_source["committee_meetings"] if i["title"] == "IQAC Plan Meet")
    assert meet["subtitle"] == "IQAC Productivity"
    assert any(i["title"].endswith("— starts") for i in by_source["research_projects"])
    assert any(i["kind"] == "milestone" and i["date"] == d(1) for i in by_source["grant_milestones"])
    assert any(i["kind"] == "installment" for i in by_source["grant_milestones"])
    assert any(i["title"] == "Linear Algebra" and i["start_time"] == "09:00" for i in by_source["teaching"])
    assert any(i["title"] == "Problem Set 4" for i in by_source["assignments"])
    assert any(i["kind"] == "session" for i in by_source["attendance_sessions"])
    assert any("PO PO-9" in i["title"] for i in by_source["finance_due"])
    assert any("Bill B-3" in i["title"] for i in by_source["finance_due"])
    assert any(i["title"] == "Prepare AQAR annexure" for i in by_source["reports_due"])


def test_calendar_feed_guards_and_source_filter(client: TestClient, world: dict):
    r = client.get(f"{API}/productivity/calendar", params={
        "date_from": d(7), "date_to": d(-2),
    })
    assert r.status_code == 422
    r = client.get(f"{API}/productivity/calendar", params={
        "date_from": d(0), "date_to": d(5), "sources": "personal,nope",
    })
    assert r.status_code == 422
    r = client.get(f"{API}/productivity/calendar", params={
        "date_from": d(0), "date_to": d(7), "sources": "events",
    })
    assert r.status_code == 200
    feed = r.json()
    assert feed["sources"] == ["events"]
    assert all(i["source"] == "events" for i in feed["items"])

    # Personal entries ride the feed too.
    r = client.post(f"{API}/productivity/calendar-entries", json={
        "title": "Dentist", "uploaded_by": "test", "start_date": TODAY,
        "start_time": "17:00",
    })
    assert r.status_code == 201, r.text
    r = client.get(f"{API}/productivity/calendar", params={
        "date_from": d(0), "date_to": d(7), "sources": "personal",
    })
    assert any(i["title"] == "Dentist" for i in r.json()["items"])


def test_reminders_and_dashboard(client: TestClient, world: dict):
    r = client.get(f"{API}/productivity/reminders", params={"as_of": TODAY})
    assert r.status_code == 200, r.text
    buckets = r.json()
    overdue_titles = {i["title"] for i in buckets["overdue"]}
    assert "Prepare AQAR annexure" in overdue_titles
    assert "Bill B-3 payable" in overdue_titles
    tomorrow_titles = {i["title"] for i in buckets["tomorrow"]}
    assert "Interim report" in tomorrow_titles
    assert "PO PO-9 delivery" in tomorrow_titles
    today_titles = {i["title"] for i in buckets["upcoming_today"]}
    assert {"Mathematics Day", "IQAC Plan Meet", "Linear Algebra"} <= today_titles

    r = client.get(f"{API}/productivity/dashboard", params={"as_of": TODAY})
    assert r.status_code == 200, r.text
    dash = r.json()
    assert dash == {
        "todays_tasks": 0,
        "upcoming_deadlines": dash["upcoming_deadlines"],
        "upcoming_meetings": 2,
        "unread_notifications": 0,
        "overdue_items": 2,
        "completed_today": 0,
    }
    assert dash["upcoming_deadlines"] >= 3  # milestone + PO + installment(+…)


def test_tasks_full_lifecycle(client: TestClient, world: dict):
    r = client.post(f"{API}/productivity/tasks", json={
        "title": "Review chapter proofs", "uploaded_by": "me", "priority": "high",
        "category": "research", "due_date": TODAY, "pinned": True,
        "tags": ["reading"], "description": "sections 1-3",
    })
    assert r.status_code == 201, r.text
    task = r.json()
    assert task["metadata"]["task_scope"] == "personal"
    assert task["priority"] == "high" and task["pinned"] is True

    # 409 on same title + due date.
    r = client.post(f"{API}/productivity/tasks", json={
        "title": "Review chapter proofs", "uploaded_by": "me", "due_date": TODAY,
    })
    assert r.status_code == 409

    # 422s: bad date / bad priority / start after due.
    for body in (
        {"title": "x", "uploaded_by": "me", "due_date": "tomorrow"},
        {"title": "x", "uploaded_by": "me", "priority": "urgent"},
        {"title": "x", "uploaded_by": "me", "start_date": d(5), "due_date": d(1)},
    ):
        r = client.post(f"{API}/productivity/tasks", json=body)
        assert r.status_code == 422, body

    # Complete -> appears in dashboard completed_today; overdue flips correctly.
    r = client.patch(f"{API}/productivity/tasks/{task['id']}", json={"completed": True})
    assert r.status_code == 200, r.text
    assert r.json()["completed"] is True
    dash = client.get(f"{API}/productivity/dashboard", params={"as_of": TODAY}).json()
    assert dash["completed_today"] == 1

    # Lists: filters + pinned-first ordering.
    r = client.get(f"{API}/productivity/tasks", params={"completed": False})
    assert all(i["completed"] is False for i in r.json()["items"])
    r = client.get(f"{API}/productivity/tasks", params={"q": "chapter"})
    assert r.json()["total_count"] == 1  # search spans completed rows too
    assert r.json()["items"][0]["completed"] is True
    r_all = client.get(f"{API}/productivity/tasks", params={"q": "proofs"})
    assert r_all.json()["total_count"] == 1

    # The committee action is NOT a personal task: 404 on task routes.
    r = client.patch(f"{API}/productivity/tasks/{world['action']}", json={"title": "hijack"})
    assert r.status_code == 404
    r = client.delete(f"{API}/productivity/tasks/{world['action']}")
    assert r.status_code == 404

    r = client.delete(f"{API}/productivity/tasks/{task['id']}")
    assert r.status_code == 204
    r = client.get(f"{API}/productivity/tasks/{task['id']}")
    assert r.status_code == 404


def test_entries_full_lifecycle(client: TestClient, world: dict):
    r = client.post(f"{API}/productivity/calendar-entries", json={
        "title": "Conference travel", "uploaded_by": "me", "start_date": d(5),
        "end_date": d(6), "location": "Chennai", "category": "events",
    })
    assert r.status_code == 201, r.text
    entry = r.json()
    assert entry["start_date"] == d(5) and entry["category"] == "events"

    r = client.post(f"{API}/productivity/calendar-entries", json={
        "title": "Conference travel", "uploaded_by": "me", "start_date": d(5),
    })
    assert r.status_code == 409
    r = client.post(f"{API}/productivity/calendar-entries", json={
        "title": "bad", "uploaded_by": "me", "start_date": d(6), "end_date": d(5),
    })
    assert r.status_code == 422

    # Merge re-check: start (d5) with a new end before it -> 422.
    r = client.patch(f"{API}/productivity/calendar-entries/{entry['id']}", json={"end_date": d(4)})
    assert r.status_code == 422
    r = client.patch(f"{API}/productivity/calendar-entries/{entry['id']}", json={"start_time": "08:30", "end_time": "09:00"})
    assert r.status_code == 200
    assert r.json()["start_time"] == "08:30"

    r = client.get(f"{API}/productivity/calendar-entries", params={"date_from": d(5), "date_to": d(5)})
    assert r.json()["total_count"] == 1
    r = client.delete(f"{API}/productivity/calendar-entries/{entry['id']}")
    assert r.status_code == 204
    r = client.get(f"{API}/productivity/calendar-entries/{entry['id']}")
    assert r.status_code == 404


def test_notifications_states_and_refresh(client: TestClient, world: dict):
    # Manual notification.
    r = client.post(f"{API}/productivity/notifications", json={
        "title": "Call the library", "uploaded_by": "me", "body": "renew books",
        "category": "task", "priority": "high", "link": "/productivity",
    })
    assert r.status_code == 201, r.text
    note = r.json()
    assert note["is_read"] is False and note["generated_by"] == "user"

    r = client.patch(f"{API}/productivity/notifications/{note['id']}", json={"is_read": True})
    assert r.json()["is_read"] is True and r.json()["read_at"]
    r = client.patch(f"{API}/productivity/notifications/{note['id']}", json={"pinned": True})
    assert r.json()["pinned"] is True
    r = client.patch(f"{API}/productivity/notifications/{note['id']}", json={"snoozed_until": "2999-01-01"})
    assert r.json()["snoozed"] is True

    listing = client.get(f"{API}/productivity/notifications", params={"state": "snoozed"}).json()
    assert listing["total_count"] == 1
    listing = client.get(f"{API}/productivity/notifications").json()  # default: active only
    assert listing["total_count"] == 0
    r = client.patch(f"{API}/productivity/notifications/{note['id']}", json={"snoozed_until": ""})
    assert r.json()["snoozed"] is False

    # Idempotent engine sweep; archived notifications never resurrect.
    first = client.post(f"{API}/productivity/notifications/refresh", json={"uploaded_by": "me"}).json()
    assert first["created"] > 0 and first["skipped_existing"] == 0
    second = client.post(f"{API}/productivity/notifications/refresh", json={"uploaded_by": "me"}).json()
    assert second["created"] == 0
    assert second["skipped_existing"] == second["considered"]

    unread = client.get(f"{API}/productivity/notifications", params={"state": "unread"}).json()
    assert unread["unread_count"] == first["created"]
    target = unread["items"][0]
    r = client.patch(f"{API}/productivity/notifications/{target['id']}", json={"archived": True})
    assert r.json()["archived"] is True
    third = client.post(f"{API}/productivity/notifications/refresh", json={"uploaded_by": "me"}).json()
    assert third["created"] == 0

    r = client.patch(f"{API}/productivity/notifications/{note['id']}", json={"snoozed_until": "next friday"})
    assert r.status_code == 422
    r = client.delete(f"{API}/productivity/notifications/{note['id']}")
    assert r.status_code == 204
    r = client.patch(f"{API}/productivity/notifications/{note['id']}", json={"is_read": True})
    assert r.status_code == 404


def test_unified_search(client: TestClient, world: dict):
    r = client.post(f"{API}/productivity/tasks", json={
        "title": "Grade midterm scripts", "uploaded_by": "me", "priority": "high",
        "category": "teaching", "due_date": d(1),
    })
    assert r.status_code == 201

    r = client.get(f"{API}/productivity/search", params={"q": "midterm"})
    assert r.status_code == 200, r.text
    hits = r.json()
    # One logical item surfaces from both lenses: the task itself + its
    # personal calendar-feed occurrence on the due date.
    assert {h["source"] for h in hits["items"]} == {"tasks", "personal"}
    assert any(h["source"] == "tasks" and h["title"] == "Grade midterm scripts" for h in hits["items"])

    r = client.get(f"{API}/productivity/search", params={
        "q": "midterm", "source": "tasks", "priority": "low",
    })
    assert r.json()["total_count"] == 0
    r = client.get(f"{API}/productivity/search", params={
        "source": "calendar", "date_from": TODAY, "date_to": TODAY,
    })
    sources = {h["source"] for h in r.json()["items"]}
    assert "events" in sources and "committee_meetings" in sources
    r = client.get(f"{API}/productivity/search", params={"date_from": d(9), "date_to": d(1)})
    assert r.status_code == 422
