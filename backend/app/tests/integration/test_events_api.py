"""Integration tests for the Events & Academic Activities API.

Mirrors ``test_finance_api.py``: in-memory SQLite (StaticPool) through the
real SQLAlchemy repository adapter, so the full stack — FastAPI routes,
mappers, use cases, domain, persistence — is exercised without PostgreSQL,
disk state, or network. Linked Objects (faculty, students, projects, grants,
committees, publications, documents) are built through the FROZEN modules'
own APIs.
"""
from __future__ import annotations
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.entities.object import UniversalObject
from app.api.dependencies.auth import get_current_user

import io

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
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


API = "/api/v1"


def _event(client, title="National Mathematics Day 2026", **overrides):
    body = {
        "title": title,
        "uploaded_by": "faculty:1",
        "status": "active",
        "event_code": "EVT-2026-001",
        "event_type": "mathematics_day",
        "organizer": "Dept. of Mathematics",
        "co_organizer": "Math Club",
        "venue": "Auditorium A",
        "mode": "offline",
        "start_date": "2026-12-22",
        "end_date": "2026-12-23",
        "department": "Mathematics",
        "school": "School of Sciences",
        "description": "Ramanujan birth anniversary celebrations.",
        "objectives": "Popularise mathematics.",
        "outcome": "Poster competition and quiz.",
        "event_status": "planned",
        "priority": "high",
        "tags": ["outreach"],
        "registration": {"expected_participants": 200, "registered": 150},
    }
    body.update(overrides)
    return client.post(f"{API}/events", json=body)


def _faculty(client, name="Dr. Meera Krishnan", employee_id="F-EVT-1"):
    return client.post(
        f"{API}/faculty",
        json={"name": name, "employee_id": employee_id, "uploaded_by": "registrar:1"},
    ).json()


def _student(client, name="Asha Verma", roll="EVT-PG-1"):
    return client.post(
        f"{API}/students",
        json={"name": name, "student_type": "pg", "roll_number": roll,
              "uploaded_by": "registrar:1"},
    ).json()


def _project(client, title="Algebraic Graphs"):
    return client.post(
        f"{API}/research/projects",
        json={"title": title, "uploaded_by": "registrar:1", "lifecycle_status": "active",
              "budget_approved": 250000},
    ).json()


def _grant(client, title="SERB Travel Grant"):
    return client.post(
        f"{API}/research/grants",
        json={"title": title, "grant_number": "SERB-EVT-1", "uploaded_by": "registrar:1",
              "amount": 50000},
    ).json()


def _committee(client, name="Cultural Committee"):
    return client.post(
        f"{API}/committees",
        json={"name": name, "committee_code": "CC-EVT-1", "committee_type": "cultural",
              "uploaded_by": "registrar:1", "status": "active"},
    ).json()


def _publication(client, title="Ramsey Bounds for Cycles"):
    return client.post(
        f"{API}/publications",
        json={"title": title, "publication_type": "conference_paper",
              "uploaded_by": "registrar:1", "authors": [{"name": "M. Krishnan"}]},
    ).json()


def _document(client, title="Certificate.pdf", object_id=None):
    data = {"title": title, "document_type": "pdf", "uploaded_by": "faculty:1"}
    if object_id:
        data["object_id"] = object_id
    return client.post(
        f"{API}/documents",
        files={"file": ("certificate.pdf", io.BytesIO(b"%PDF-1.4 cert"), "application/pdf")},
        data=data,
    ).json()


# ---------------------------------------------------------------------------
# PART 1 record + PARTS 2-5 sections + PART 8 presentations + link groups
# ---------------------------------------------------------------------------
def test_event_full_create_get_and_enrichment(client):
    faculty = _faculty(client)
    student = _student(client)
    project = _project(client)
    grant = _grant(client)
    committee = _committee(client)
    publication = _publication(client)

    created = _event(client)
    assert created.status_code == 201, created.text
    event = created.json()
    event_id = event["id"]

    certificate = _document(client, object_id=event_id)
    photo = _document(client, title="Photo.png", object_id=event_id)
    assert "id" in certificate and "id" in photo

    enriched = client.put(
        f"{API}/events/{event_id}",
        json={
            "uploaded_by": "faculty:1",
            "participation": [
                {
                    "role": "organizer",
                    "contribution": "Convened the organising team",
                    "certificate_document_id": certificate["id"],
                    "remarks": "Certificate received at valedictory.",
                }
            ],
            "speakers": [
                {
                    "name": "Prof. S. Raman",
                    "affiliation": "IIT Delhi",
                    "designation": "Professor",
                    "email": "raman@iitd.example",
                    "phone": "9810012345",
                    "biography": "Works on combinatorial number theory.",
                    "photo_document_id": photo["id"],
                    "document_ids": [certificate["id"]],
                }
            ],
            "presentations": [
                {"publication_id": publication["id"], "relation": "presented_paper",
                 "remarks": "Best session talk."}
            ],
            "links": {
                "faculty": [faculty["id"]],
                "students": [student["id"]],
                "projects": [project["id"]],
                "grants": [grant["id"]],
                "committees": [committee["id"]],
            },
        },
    )
    assert enriched.status_code == 200, enriched.text
    body = enriched.json()
    speaker_row_id = body["speakers"][0]["row_id"]
    assert speaker_row_id

    schedule = client.put(
        f"{API}/events/{event_id}",
        json={
            "uploaded_by": "faculty:1",
            "schedule": [
                {
                    "title": "Keynote: Ramanujan's Legacy",
                    "session_date": "2026-12-22",
                    "start_time": "10:00",
                    "end_time": "11:00",
                    "speaker_id": speaker_row_id,
                    "venue": "Auditorium A",
                    "chairperson": "Dr. Meera Krishnan",
                    "remarks": "Followed by quiz finals.",
                }
            ],
        },
    )
    assert schedule.status_code == 200, schedule.text

    fetched = client.get(f"{API}/events/{event_id}").json()
    assert fetched["event_code"] == "EVT-2026-001"
    assert fetched["event_type"] == "mathematics_day"
    assert fetched["mode"] == "offline"
    assert fetched["tags"] == ["outreach"]
    assert fetched["registration"]["expected_participants"] == 200
    assert fetched["participation"][0]["certificate"] == {
        "id": certificate["id"], "title": "Certificate.pdf"
    }
    assert fetched["speakers"][0]["photo"] == {"id": photo["id"], "title": "Photo.png"}
    assert fetched["speakers"][0]["supporting_documents"] == [
        {"id": certificate["id"], "title": "Certificate.pdf"}
    ]
    assert fetched["schedule"][0]["speaker_name"] == "Prof. S. Raman"
    assert fetched["presentations"][0]["publication_title"] == publication["title"]
    assert fetched["stats"] == {
        "participation": 1, "speakers": 1, "sessions": 1,
        "presentations": 1, "certificates": 1,
    }
    assert [link["id"] for link in fetched["links"]["faculty"]] == [faculty["id"]]
    assert [link["id"] for link in fetched["links"]["students"]] == [student["id"]]
    assert [link["id"] for link in fetched["links"]["projects"]] == [project["id"]]
    assert [link["id"] for link in fetched["links"]["grants"]] == [grant["id"]]
    assert [link["id"] for link in fetched["links"]["committees"]] == [committee["id"]]
    assert [link["id"] for link in fetched["links"]["publications"]] == [publication["id"]]

    # List rows carry the same denormalised shape as the workspace payload
    # (the one shared enrichment — resolved speaker name included).
    listed = client.get(f"{API}/events").json()
    row = next(item for item in listed["items"] if item["id"] == event_id)
    assert row["schedule"][0]["speaker_name"] == "Prof. S. Raman"
    assert row["participation"][0]["certificate"]["id"] == certificate["id"]
    assert row["stats"]["certificates"] == 1


def test_event_duplicate_guards_and_reference_validation(client):
    created = _event(client)
    assert created.status_code == 201, created.text

    duplicate_code = _event(client, title="A Different Event")
    assert duplicate_code.status_code == 409
    duplicate_triple = _event(client, event_code=None)
    assert duplicate_triple.status_code == 409

    faculty = _faculty(client)
    bad_presentation = _event(
        client, title="Bad Presentation", event_code=None,
        presentations=[{"publication_id": faculty["id"]}],
    )
    assert bad_presentation.status_code == 422
    bad_speaker_ref = _event(
        client, title="Bad Speaker Ref", event_code=None,
        speakers=[{"name": "Prof. X"}],
        schedule=[{"title": "Session", "speaker_id": "ghost"}],
    )
    assert bad_speaker_ref.status_code == 422
    bad_certificate = _event(
        client, title="Bad Certificate", event_code=None,
        participation=[{"role": "organizer", "certificate_document_id": faculty["id"]}],
    )
    assert bad_certificate.status_code == 422
    bad_link = _event(
        client, title="Bad Link", event_code=None, links={"students": [faculty["id"]]},
    )
    assert bad_link.status_code == 422
    bad_year = client.get(f"{API}/events", params={"year": "26"})
    assert bad_year.status_code == 422


def test_event_wire_validation_errors(client):
    bad_type = _event(client, title="Bad Type", event_code=None, event_type="mega_fest")
    assert bad_type.status_code == 422
    bad_mode = _event(client, title="Bad Mode", event_code=None, mode="telepathic")
    assert bad_mode.status_code == 422
    bad_dates = _event(client, title="Bad Dates", event_code=None, end_date="2026-12-21")
    assert bad_dates.status_code == 422
    bad_role = _event(
        client, title="Bad Role", event_code=None, participation=[{"role": "boss"}]
    )
    assert bad_role.status_code == 422
    bad_time = _event(
        client, title="Bad Time", event_code=None,
        schedule=[{"title": "S", "start_time": "noon"}],
    )
    assert bad_time.status_code == 422
    bad_time_order = _event(
        client, title="Bad Time Order", event_code=None,
        schedule=[{"title": "S", "start_time": "12:00", "end_time": "09:00"}],
    )
    assert bad_time_order.status_code == 422
    bad_registration = _event(
        client, title="Bad Registration", event_code=None, registration={"present": -1}
    )
    assert bad_registration.status_code == 422
    bad_registration_key = _event(
        client, title="Bad Registration Key", event_code=None, registration={"attendees": 5}
    )
    assert bad_registration_key.status_code == 422
    bad_section_key = _event(
        client, title="Bad Speaker Key", event_code=None, speakers=[{"name": "X", "age": 5}]
    )
    assert bad_section_key.status_code == 422


def test_event_search_and_filters(client):
    _event(client, title="Algebra Colloquium", event_code="E-A1",
           event_type="research_colloquium", department="Mathematics",
           organizer="Dept. of Mathematics", start_date="2026-01-15",
           participation=[{"role": "speaker"}])
    _event(client, title="Cloud Workshop", event_code="E-B2",
           event_type="workshop", department="Computer Science",
           organizer="CSI Student Chapter", start_date="2025-11-05",
           end_date="2025-11-06", event_status="completed",
           participation=[{"role": "participant"}])
    _event(client, title="Green Outreach", event_code="E-C3",
           event_type="outreach_activity", department="Botany",
           organizer="NSS Unit", start_date="2026-06-05", event_status="cancelled")

    assert client.get(f"{API}/events").json()["total_count"] == 3
    by_type = client.get(f"{API}/events", params={"event_type": "workshop"}).json()
    assert [item["title"] for item in by_type["items"]] == ["Cloud Workshop"]
    by_year = client.get(f"{API}/events", params={"year": "2026"}).json()
    assert {item["title"] for item in by_year["items"]} == {
        "Algebra Colloquium", "Green Outreach"
    }
    by_role = client.get(f"{API}/events", params={"role": "participant"}).json()
    assert [item["title"] for item in by_role["items"]] == ["Cloud Workshop"]
    by_dept = client.get(f"{API}/events", params={"department": "computer"}).json()
    assert [item["title"] for item in by_dept["items"]] == ["Cloud Workshop"]
    by_organizer = client.get(f"{API}/events", params={"organizer": "nss"}).json()
    assert [item["title"] for item in by_organizer["items"]] == ["Green Outreach"]
    by_status = client.get(f"{API}/events", params={"status": "cancelled"}).json()
    assert [item["title"] for item in by_status["items"]] == ["Green Outreach"]
    by_q = client.get(f"{API}/events", params={"q": "cloud workshop"}).json()
    assert [item["title"] for item in by_q["items"]] == ["Cloud Workshop"]
    by_code = client.get(f"{API}/events", params={"q": "E-A1"}).json()
    assert [item["title"] for item in by_code["items"]] == ["Algebra Colloquium"]
    pagination = client.get(f"{API}/events", params={"page": 2, "page_size": 2}).json()
    assert pagination["total_count"] == 3 and len(pagination["items"]) == 1


def test_event_update_merge_contract_and_patch_alias(client):
    created = _event(client)
    event = created.json()

    updated = client.put(
        f"{API}/events/{event['id']}",
        json={
            "uploaded_by": "faculty:1",
            "venue": "Seminar Hall B",
            "event_status": "ongoing",
            "registration": {"present": 87},
            "tags": ["annual", "outreach"],
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    # Replaced fields…
    assert body["venue"] == "Seminar Hall B"
    assert body["event_status"] == "ongoing"
    assert body["tags"] == ["annual", "outreach"]
    assert body["registration"] == {
        "expected_participants": 0, "registered": 0, "present": 87, "certificates_issued": 0
    }
    # …untouched fields preserved.
    assert body["event_code"] == "EVT-2026-001"
    assert body["organizer"] == "Dept. of Mathematics"
    assert body["priority"] == "high"
    assert body["version"] > event["version"]

    # PATCH is the same handler (status-flip idiom).
    patched = client.patch(
        f"{API}/events/{event['id']}",
        json={"uploaded_by": "faculty:1", "event_status": "completed", "outcome": "Held."},
    )
    assert patched.status_code == 200
    assert patched.json()["event_status"] == "completed"
    assert patched.json()["outcome"] == "Held."


def test_event_update_duplicate_rescan_and_links_group_replace(client):
    _event(client, title="First", event_code="E-DUP-1")
    second = _event(client, title="Second", event_code="E-DUP-2").json()
    clash = client.put(
        f"{API}/events/{second['id']}",
        json={"uploaded_by": "faculty:1", "event_code": "E-DUP-1"},
    )
    assert clash.status_code == 409

    faculty = _faculty(client)
    project = _project(client)
    linked = client.put(
        f"{API}/events/{second['id']}",
        json={"uploaded_by": "faculty:1",
              "links": {"faculty": [faculty["id"]], "projects": [project["id"]]}},
    )
    assert linked.status_code == 200, linked.text
    assert [link["id"] for link in linked.json()["links"]["faculty"]] == [faculty["id"]]

    # The links object is a WHOLE-links replace across every input group (the
    # finance precedent): groups absent from it are cleared, and the
    # presentations-derived publications edges are never touched by links.
    replaced = client.put(
        f"{API}/events/{second['id']}",
        json={"uploaded_by": "faculty:1", "links": {"faculty": []}},
    )
    assert replaced.status_code == 200
    assert replaced.json()["links"]["faculty"] == []
    assert replaced.json()["links"]["projects"] == []

    # No links key at all -> every group is left untouched (merge contract).
    relinked = client.put(
        f"{API}/events/{second['id']}",
        json={"uploaded_by": "faculty:1", "links": {"projects": [project["id"]],
              "faculty": [faculty["id"]], "students": [], "grants": [],
              "committees": []}},
    )
    assert relinked.status_code == 200
    scalar_only = client.put(
        f"{API}/events/{second['id']}",
        json={"uploaded_by": "faculty:1", "venue": "Room 9"},
    )
    assert scalar_only.status_code == 200
    assert [link["id"] for link in scalar_only.json()["links"]["projects"]] == [project["id"]]
    assert [link["id"] for link in scalar_only.json()["links"]["faculty"]] == [faculty["id"]]


def test_event_schedule_speaker_lifecycle(client):
    created = client.put(
        f"{API}/events/{_event(client).json()['id']}",
        json={"uploaded_by": "faculty:1", "speakers": [{"name": "Prof. S. Raman"}]},
    )
    assert created.status_code == 200, created.text
    event = created.json()
    row_id = event["speakers"][0]["row_id"]

    with_session = client.put(
        f"{API}/events/{event['id']}",
        json={"uploaded_by": "faculty:1",
              "schedule": [{"title": "Keynote", "start_time": "10:00",
                            "speaker_id": row_id}]},
    )
    assert with_session.status_code == 200, with_session.text
    assert with_session.json()["schedule"][0]["speaker_name"] == "Prof. S. Raman"

    renamed = client.put(
        f"{API}/events/{event['id']}",
        json={"uploaded_by": "faculty:1",
              "speakers": [{"row_id": row_id, "name": "Prof. S. Raman (IITD)"}]},
    )
    assert renamed.status_code == 200
    assert renamed.json()["schedule"][0]["speaker_name"] == "Prof. S. Raman (IITD)"

    # A session referencing a row absent from the payload speakers -> 422.
    stale = client.put(
        f"{API}/events/{event['id']}",
        json={"uploaded_by": "faculty:1",
              "speakers": [{"name": "Someone Else"}],
              "schedule": [{"title": "Keynote", "speaker_id": row_id}]},
    )
    assert stale.status_code == 422


def test_events_dashboard_exact_counts(client):
    base = client.get(f"{API}/events/dashboard").json()
    publication = _publication(client)
    certificate = _document(client)

    _event(client, title="Conference A", event_code="E-DA", event_type="conference",
           event_status="planned",
           participation=[{"role": "convener",
                           "certificate_document_id": certificate["id"]}],
           presentations=[{"publication_id": publication["id"],
                           "relation": "poster_presentation"}])
    _event(client, title="Workshop B", event_code="E-DB", event_type="workshop",
           event_status="ongoing", participation=[{"role": "attendee"}])
    _event(client, title="Talk C", event_code="E-DC", event_type="invited_talk",
           event_status="completed", participation=[{"role": "speaker"}])
    _event(client, title="Seminar D", event_code="E-DD", event_status="cancelled")

    cards = client.get(f"{API}/events/dashboard").json()
    assert cards["upcoming_events"] - base["upcoming_events"] == 2
    assert cards["completed_events"] - base["completed_events"] == 1
    assert cards["events_organized"] - base["events_organized"] == 1
    assert cards["events_attended"] - base["events_attended"] == 1
    assert cards["certificates"] - base["certificates"] == 1
    assert cards["presentations"] - base["presentations"] == 1
    assert cards["invited_talks"] - base["invited_talks"] == 1


def test_event_delete_and_404_guards(client):
    event = _event(client).json()
    assert client.delete(f"{API}/events/{event['id']}").status_code == 204
    assert client.get(f"{API}/events/{event['id']}").status_code == 404
    assert client.delete(f"{API}/events/{event['id']}").status_code == 404

    faculty = _faculty(client)
    assert client.get(f"{API}/events/{faculty['id']}").status_code == 404
    assert client.delete(f"{API}/events/{faculty['id']}").status_code == 404
