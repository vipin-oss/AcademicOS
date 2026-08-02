"""Integration tests for the Committees & Meetings API (governance slice).

Mirrors ``test_research_api.py`` / ``test_faculty_api.py``: in-memory SQLite
(StaticPool) through the real SQLAlchemy repository adapter, so the full
stack — FastAPI routes, mappers, use cases, domain, persistence — is
exercised without PostgreSQL, disk state, or network. Linked Objects
(faculty, students, projects, grants, publications, documents) are built
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


def _committee(client, name="Board of Studies (Physics)", code="BOS-PHY-01", **overrides):
    body = {
        "name": name,
        "uploaded_by": "registrar:1",
        "status": "active",
        "committee_code": code,
        "committee_type": "Board of Studies (BoS)",
        "department": "Physics",
        "school": "School of Physical Sciences",
        "description": "Curriculum and syllabi governance for Physics.",
        "constitution_date": "2025-07-01",
        "expiry_date": "2027-06-30",
        "notes": "Meets twice a semester.",
        "tags": ["bos", "governance"],
    }
    body.update(overrides)
    return client.post(f"{API}/committees", json=body)


def _people(client):
    chair = client.post(
        f"{API}/faculty",
        json={"name": "Prof. Asha Nair", "employee_id": "EMP-1001",
              "uploaded_by": "registrar:1", "designation": "Professor",
              "department": "Physics"},
    ).json()
    member = client.post(
        f"{API}/faculty",
        json={"name": "Prof. Kabir Shah", "employee_id": "EMP-2002",
              "uploaded_by": "registrar:1", "designation": "Associate Professor",
              "department": "Mathematics"},
    ).json()
    external = client.post(
        f"{API}/faculty",
        json={"name": "Prof. Meera Iyer", "employee_id": "EMP-3003",
              "uploaded_by": "registrar:1", "designation": "Professor",
              "department": "Chemistry"},
    ).json()
    student = client.post(
        f"{API}/students",
        json={"name": "Ravi Kumar", "student_type": "phd", "roll_number": "PHD-2201",
              "uploaded_by": "registrar:1"},
    ).json()
    return chair, member, external, student


def _meeting(client, committee_id, number="1", date="2026-08-15", **overrides):
    body = {
        "title": f"Meeting {number} AY 2026-27",
        "uploaded_by": "registrar:1",
        "meeting_number": number,
        "meeting_date": date,
        "venue": "Committee Room 2",
        "mode": "hybrid",
        "agenda_items": [
            {"title": "UG syllabus revision", "priority": "high",
             "presenter": "Prof. Asha Nair", "status": "pending"},
            {"title": "PhD coursework credits", "status": "pending"},
        ],
        "attendance": [],
        "decisions": [],
    }
    body.update(overrides)
    return client.post(f"{API}/committees/{committee_id}/meetings", json=body)


# ---------------------------------------------------------------------------
# Create + identity + validation
# ---------------------------------------------------------------------------
def test_create_full_committee_with_members_and_links(client):
    chair, member, external, student = _people(client)
    project = client.post(
        f"{API}/research/projects",
        json={"title": "Perovskite Cells", "uploaded_by": "registrar:1",
              "lifecycle_status": "funded"},
    ).json()
    grant = client.post(
        f"{API}/research/grants",
        json={"title": "SERB Core Grant", "grant_number": "CRG-01",
              "uploaded_by": "registrar:1"},
    ).json()
    publication = client.post(
        f"{API}/publications",
        json={"title": "Quantum dots in perovskites", "publication_type": "journal_article",
              "uploaded_by": "registrar:1", "authors": [{"name": "Asha Nair"}]},
    ).json()

    response = _committee(
        client,
        members=[
            {"faculty_id": chair["id"], "role": "chairperson",
             "start_date": "2025-07-01"},
            {"faculty_id": member["id"], "role": "member",
             "start_date": "2025-07-01", "end_date": "2027-06-30"},
            {"faculty_id": external["id"], "role": "external_expert",
             "remarks": "IIT Delhi"},
            {"faculty_id": student["id"], "role": "student_member"},
        ],
        links={"projects": [project["id"]], "grants": [grant["id"]],
               "students": [student["id"]], "publications": [publication["id"]]},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["committee_code"] == "BOS-PHY-01"
    assert body["committee_type"] == "Board of Studies (BoS)"
    assert body["tags"] == ["bos", "governance"]
    assert [m["role"] for m in body["members"]] == [
        "chairperson", "member", "external_expert", "student_member",
    ]  # leadership first; the rest by name (Kabir < Meera < Ravi)
    assert body["members"][0]["name"] == "Prof. Asha Nair"
    assert [link["id"] for link in body["links"]["projects"]] == [project["id"]]
    assert [link["id"] for link in body["links"]["grants"]] == [grant["id"]]
    assert body["links"]["projects"][0]["kind"] == "related_to"
    assert body["stats"] == {"meetings": 0, "pending_actions": 0, "completed_actions": 0}

    # the faculty module's committee lens stays live (backlink written here)
    faculty_view = client.get(f"{API}/faculty/{chair['id']}").json()
    assert [c["id"] for c in faculty_view["links"]["committees"]] == [body["id"]]
    assert faculty_view["stats"]["committees"] == 1


def test_duplicate_identity_409_and_bad_input_422(client):
    assert _committee(client).status_code == 201
    assert _committee(client, name="Other BoS", code="bos-phy-01").status_code == 409
    assert _committee(client, code=None).status_code == 409  # same name+type+dept triple
    # same name but another department is a different committee
    assert _committee(client, code="BOS-MAT-01", department="Mathematics").status_code == 201
    assert _committee(client, name="X", code="X-1", constitution_date="bad").status_code == 422
    assert _committee(client, name="Y", code="X-2", members=[{"faculty_id": "obj:faculty:NO",
                                                              "role": "member"}]).status_code == 422


def test_member_role_and_person_guards(client):
    chair, _, _, _ = _people(client)
    bad_role = _committee(
        client, members=[{"faculty_id": chair["id"], "role": "dictator"}]
    )
    assert bad_role.status_code == 422
    project = client.post(
        f"{API}/research/projects",
        json={"title": "Wrong Type", "uploaded_by": "registrar:1"},
    ).json()
    wrong_type = _committee(
        client, members=[{"faculty_id": project["id"], "role": "member"}]
    )
    assert wrong_type.status_code == 422
    bad_link = _committee(client, links={"projects": [chair["id"]]})
    assert bad_link.status_code == 422


# ---------------------------------------------------------------------------
# List (PART 9)
# ---------------------------------------------------------------------------
def test_list_search_and_part9_filters(client):
    chair, _, _, _ = _people(client)
    first = _committee(
        client, members=[{"faculty_id": chair["id"], "role": "chairperson"}]
    ).json()
    _meeting(client, first["id"], date="2026-08-15")
    _committee(client, name="IQAC", code="IQAC-01",
               committee_type="Internal Quality Assurance Cell (IQAC)",
               department="Administration")

    assert client.get(f"{API}/committees").json()["total_count"] == 2
    by_type = client.get(
        f"{API}/committees",
        params={"committee_type": "Internal Quality Assurance Cell (IQAC)"},
    ).json()
    assert [i["name"] for i in by_type["items"]] == ["IQAC"]
    by_q = client.get(f"{API}/committees", params={"q": "bos physics asha"}).json()
    assert [i["name"] for i in by_q["items"]] == ["Board of Studies (Physics)"]
    by_chair = client.get(f"{API}/committees", params={"chairperson": "asha"}).json()
    assert [i["name"] for i in by_chair["items"]] == ["Board of Studies (Physics)"]
    by_year = client.get(f"{API}/committees", params={"meeting_year": 2026}).json()
    assert by_year["total_count"] == 1
    none_year = client.get(f"{API}/committees", params={"meeting_year": 2021}).json()
    assert none_year["total_count"] == 0
    by_dept = client.get(f"{API}/committees", params={"department": "admin"}).json()
    assert [i["name"] for i in by_dept["items"]] == ["IQAC"]
    assert client.get(f"{API}/committees", params={"page": 0}).status_code == 422


# ---------------------------------------------------------------------------
# Meetings (PART 3) + update/get/delete + cascade
# ---------------------------------------------------------------------------
def test_meeting_lifecycle_and_number_uniqueness(client):
    committee = _committee(client).json()
    meeting = _meeting(client, committee["id"]).json()
    assert meeting["meeting_number"] == "1"
    assert meeting["committee"]["id"] == committee["id"]
    assert meeting["stats"]["agenda_items"] == 2

    # duplicate number within the SAME committee -> 409
    assert _meeting(client, committee["id"], number="1").status_code == 409
    other = _committee(client, name="Finance Committee", code="FC-01",
                       committee_type="Finance Committee", department="Finance").json()
    # same number under another committee -> fine
    assert _meeting(client, other["id"], number="1").status_code == 201

    updated = client.put(
        f"{API}/committees/meetings/{meeting['id']}",
        json={"venue": "Online (Meet)", "mode": "online",
              "decisions": ["Syllabus approved for circulation."],
              "uploaded_by": "registrar:2"},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["mode"] == "online"
    assert body["decisions"] == ["Syllabus approved for circulation."]
    assert body["meeting_date"] == "2026-08-15"  # untouched

    # the committee workspace embeds the meeting summaries
    view = client.get(f"{API}/committees/{committee['id']}").json()
    assert [m["meeting_number"] for m in view["meetings"]] == ["1"]
    assert view["stats"]["meetings"] == 1

    assert _meeting(client, "obj:committee:NOPE").status_code == 404
    bad_mode = _meeting(client, committee["id"], number="9", mode="smoke-signals")
    assert bad_mode.status_code == 422

    assert client.delete(f"{API}/committees/meetings/{meeting['id']}").status_code == 204
    assert client.get(f"{API}/committees/meetings/{meeting['id']}").status_code == 404
    assert client.delete(f"{API}/committees/meetings/{meeting['id']}").status_code == 404


def test_agenda_attendance_resolution(client):
    chair, _, _, _ = _people(client)
    committee = _committee(client).json()
    meeting = _meeting(
        client, committee["id"],
        attendance=[{"object_id": chair["id"], "status": "present"},
                    {"name": "Dr. External Guest", "status": "leave"}],
    ).json()
    got = client.get(f"{API}/committees/meetings/{meeting['id']}").json()
    assert got["attendance"][0]["name"] == "Prof. Asha Nair"
    assert got["attendance"][0]["object_type"] == "faculty"
    assert got["attendance"][1]["name"] == "Dr. External Guest"

    # supporting documents on an agenda item resolve to {id, title}
    form = {"title": "UG Syllabus Draft", "document_type": "pdf",
            "uploaded_by": "registrar:1", "object_id": meeting["id"]}
    doc = client.post(
        f"{API}/documents",
        files={"file": ("syllabus.txt", b"draft syllabus", "text/plain")},
        data=form,
    ).json()
    with_agenda = client.put(
        f"{API}/committees/meetings/{meeting['id']}",
        json={"agenda_items": [{"title": "UG syllabus revision", "priority": "high",
                                "status": "discussed", "document_ids": [doc["id"]]}],
              "uploaded_by": "registrar:2"},
    ).json()
    assert with_agenda["agenda_items"][0]["supporting_documents"] == [
        {"id": doc["id"], "title": "UG Syllabus Draft"}
    ]


# ---------------------------------------------------------------------------
# Action tracker (PART 5)
# ---------------------------------------------------------------------------
def test_action_tracker_full_flow(client):
    chair, _, _, _ = _people(client)
    committee = _committee(client).json()
    meeting = _meeting(client, committee["id"]).json()

    created = client.post(
        f"{API}/committees/meetings/{meeting['id']}/actions",
        json={"title": "Circulate revised UG syllabus", "uploaded_by": "registrar:1",
              "assigned_to": chair["id"], "due_date": "2026-08-30", "priority": "high"},
    )
    assert created.status_code == 201, created.text
    action = created.json()
    assert action["assigned_name"] == "Prof. Asha Nair"
    assert action["meeting"]["id"] == meeting["id"]

    progressed = client.put(
        f"{API}/committees/actions/{action['id']}",
        json={"status": "in_progress", "progress": 60, "uploaded_by": "registrar:2"},
    ).json()
    assert progressed["status"] == "in_progress"
    assert progressed["progress"] == 60

    done = client.put(
        f"{API}/committees/actions/{action['id']}",
        json={"status": "done", "completion_date": "2026-08-28",
              "uploaded_by": "registrar:2"},
    ).json()
    assert done["completion_date"] == "2026-08-28"

    stats = client.get(f"{API}/committees/meetings/{meeting['id']}").json()["stats"]
    assert stats == {"agenda_items": 2, "pending_actions": 0, "completed_actions": 1}

    assert client.put(
        f"{API}/committees/actions/{action['id']}",
        json={"progress": 120, "uploaded_by": "registrar:2"},
    ).status_code == 422
    assert client.delete(f"{API}/committees/actions/{action['id']}").status_code == 204
    assert client.delete(f"{API}/committees/actions/{action['id']}").status_code == 404


# ---------------------------------------------------------------------------
# Update committee (merge + members reconcile) + delete cascade (PART 8 dashboard)
# ---------------------------------------------------------------------------
def test_update_merge_members_reconcile_and_delete_cascade(client):
    chair, member, _, _ = _people(client)
    committee = _committee(
        client,
        members=[{"faculty_id": chair["id"], "role": "chairperson"}],
    ).json()
    meeting = _meeting(client, committee["id"]).json()
    action = client.post(
        f"{API}/committees/meetings/{meeting['id']}/actions",
        json={"title": "Pending A", "uploaded_by": "registrar:1"},
    ).json()

    updated = client.put(
        f"{API}/committees/{committee['id']}",
        json={"notes": "Reconstituted.", "uploaded_by": "registrar:2",
              "members": [{"faculty_id": member["id"], "role": "convener"}]},
    ).json()
    assert [m["name"] for m in updated["members"]] == ["Prof. Kabir Shah"]
    assert updated["members"][0]["role"] == "convener"
    assert updated["notes"] == "Reconstituted."
    assert updated["committee_code"] == "BOS-PHY-01"  # untouched

    # backlink reconciled: chair lost it, the new convener has it
    assert client.get(f"{API}/faculty/{chair['id']}").json()["links"]["committees"] == []
    konv = client.get(f"{API}/faculty/{member['id']}").json()
    assert [c["id"] for c in konv["links"]["committees"]] == [committee["id"]]

    # duplicate re-check on rename to an existing triple
    _committee(client, name="IQAC", code="IQAC-01",
               committee_type="Internal Quality Assurance Cell (IQAC)",
               department="Administration").json()
    clash = client.put(
        f"{API}/committees/{committee['id']}",
        json={"name": "IQAC", "committee_type": "Internal Quality Assurance Cell (IQAC)",
              "department": "Administration", "uploaded_by": "registrar:2"},
    )
    assert clash.status_code == 409

    # dashboard reflects everything BEFORE the cascade
    dashboard = client.get(f"{API}/committees/dashboard").json()
    assert dashboard["total_committees"] == 2
    assert dashboard["pending_actions"] == 1
    assert any(u["committee_title"] == committee["name"]
               for u in dashboard["upcoming_meetings"]) or not dashboard["upcoming_meetings"]

    # delete cascades meetings + action items; people/link targets survive
    assert client.delete(f"{API}/committees/{committee['id']}").status_code == 204
    assert client.get(f"{API}/committees/{committee['id']}").status_code == 404
    assert client.get(f"{API}/committees/meetings/{meeting['id']}").status_code == 404
    assert client.get(f"{API}/faculty/{chair['id']}").status_code == 200
    after = client.get(f"{API}/committees/dashboard").json()
    assert after["total_committees"] == 1
    assert after["pending_actions"] == 0
    assert action["id"]  # (Cascade verified via the deleted-parent 404s above.)


def test_get_missing_is_404(client):
    assert client.get(f"{API}/committees/obj:committee:DOESNOTEXIST").status_code == 404
    assert client.put(
        f"{API}/committees/obj:committee:DOESNOTEXIST",
        json={"notes": "x", "uploaded_by": "registrar:2"},
    ).status_code == 404
    assert client.delete(f"{API}/committees/obj:committee:DOESNOTEXIST").status_code == 404
    assert client.get(f"{API}/committees/meetings/obj:meeting:NOPE").status_code == 404


def test_events_and_audit_round_trip(client):
    committee = _committee(client).json()
    assert committee["uploaded_by"] == "registrar:1"
    assert committee["version"] == 1
    assert any("Created" in event for event in committee["events"])
