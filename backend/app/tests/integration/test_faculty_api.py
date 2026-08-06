"""Integration tests for the Faculty API (Faculty Management slice).

Mirrors ``test_research_api.py``: in-memory SQLite (StaticPool) through the
real SQLAlchemy repository adapter, so the full stack — FastAPI routes,
mappers, use cases, domain, persistence — is exercised without PostgreSQL,
disk state, or network. The cross-module graph (projects, grants, students,
classes, publications) is built through the FROZEN modules' own APIs.
"""
from __future__ import annotations
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.entities.object import UniversalObject
from app.api.dependencies.auth import get_current_user

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic_settings")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.faculty import get_storage as faculty_get_storage
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.session import get_db
from app.infrastructure.storage.local import LocalFileStorage
from app.main import app


@pytest.fixture()
def client(tmp_path):
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
    app.dependency_overrides[faculty_get_storage] = lambda: LocalFileStorage(str(tmp_path))
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


API = "/api/v1"


def _faculty(client, name="Dr. Asha Nair", employee_id="EMP-1001", **overrides):
    body = {
        "name": name,
        "employee_id": employee_id,
        "uploaded_by": "registrar:1",
        "status": "active",
        "faculty_code": "PHY-A-07",
        "designation": "Associate Professor",
        "department": "Physics",
        "school": "School of Physical Sciences",
        "joining_date": "2015-07-01",
        "employment_type": "regular",
        "email": "asha.nair@univ.edu",
        "mobile": "+91-98xxxxxxx1",
        "office": "B-204",
        "qualification": "Ph.D. (Physics), IIT Delhi",
        "specialization": "Condensed Matter Physics",
        "research_interests": ["perovskites", "quantum dots"],
        "biography": "Works on thin-film photovoltaics.",
        "orcid": "0000-0002-1825-0097",
        "scopus_id": "55512345600",
        "google_scholar": "abcXYZ",
        "researchgate": "Asha-Nair-42",
        "website": "https://univ.edu/faculty/asha",
        "notes": "PhD coordinator.",
        "tags": ["senate"],
        "degrees": [{"degree": "Ph.D.", "institution": "IIT Delhi", "year": "2012"}],
        "experience": [{"role": "Assistant Professor", "organization": "Univ", "from": "2015"}],
        "awards": [{"title": "Young Scientist Award", "year": "2019", "by": "INSA"}],
        "memberships": [{"body": "Indian Physics Association"}],
        "certifications": [{"title": "Nano-fab", "issuer": "INI", "year": "2020"}],
        "admin_positions": [{"position": "PhD Coordinator", "unit": "Physics", "from": "2023"}],
    }
    body.update(overrides)
    return client.post(f"{API}/faculty", json=body)


def test_create_full_record_201(client):
    committee = client.post(
        f"{API}/objects",
        json={"object_type": "committee", "title": "IQAC", "created_by": "registrar:1"},
    ).json()
    response = _faculty(client, links={"committees": [committee["id"]]})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["employee_id"] == "EMP-1001"
    assert body["designation"] == "Associate Professor"
    assert body["research_interests"] == ["perovskites", "quantum dots"]
    assert body["degrees"][0]["institution"] == "IIT Delhi"
    assert body["admin_positions"][0]["position"] == "PhD Coordinator"
    assert [link["id"] for link in body["links"]["committees"]] == [committee["id"]]
    assert body["links"]["committees"][0]["kind"] == "member_of"
    assert body["stats"] == {
        "publications": 0, "active_projects": 0, "grants": 0,
        "students_supervised": 0, "courses": 0, "committees": 0,
    }


def test_duplicate_identity_is_409_and_bad_input_is_422(client):
    assert _faculty(client).status_code == 201
    assert _faculty(client, name="Copy", employee_id="emp-1001").status_code == 409
    assert _faculty(client, name="Copy2", employee_id="EMP-1002", faculty_code="phy-a-07").status_code == 409
    assert _faculty(client, name="NoId", employee_id="").status_code == 422
    assert _faculty(client, name="BadMail", employee_id="EMP-1003", email="nope").status_code == 422
    assert _faculty(client, name="BadType", employee_id="EMP-1004",
                    employment_type="freelance").status_code == 422
    bad_committee = client.post(
        f"{API}/objects",
        json={"object_type": "student", "title": "NotACommittee", "created_by": "registrar:1"},
    ).json()
    assert _faculty(client, name="BadLink", employee_id="EMP-1005", faculty_code=None,
                    links={"committees": [bad_committee["id"]]}).status_code == 422


def test_list_search_and_filters(client):
    _faculty(client)
    _faculty(client, name="Dr. Kabir Shah", employee_id="EMP-2002", faculty_code=None,
               designation="Professor", department="Mathematics", specialization="Algebra",
               research_interests=["number theory"])
    listing = client.get(f"{API}/faculty").json()
    assert listing["total_count"] == 2
    physics = client.get(f"{API}/faculty", params={"department": "physics"}).json()
    assert [r["name"] for r in physics["items"]] == ["Dr. Asha Nair"]
    assert client.get(f"{API}/faculty", params={"designation": "PROFESSOR"}).json()["total_count"] == 1
    found = client.get(f"{API}/faculty", params={"q": "quantum dots asha"}).json()
    assert [r["name"] for r in found["items"]] == ["Dr. Asha Nair"]
    found = client.get(f"{API}/faculty", params={"q": "algebra"}).json()
    assert [r["name"] for r in found["items"]] == ["Dr. Kabir Shah"]
    with_page = client.get(f"{API}/faculty", params={"page": 2, "page_size": 1}).json()
    assert with_page["total_count"] == 2 and len(with_page["items"]) == 1
    assert client.get(f"{API}/faculty", params={"page": 0}).status_code == 422


def test_get_enriched_workspace_and_cross_module_lenses(client):
    """The money test: build the graph through FROZEN modules' own APIs."""
    faculty = _faculty(client).json()

    project = client.post(
        f"{API}/research/projects",
        json={
            "title": "Perovskite Cells",
            "uploaded_by": "registrar:1",
            "lifecycle_status": "funded",
            "project_code": "P-01",
            "team": {"principal_investigators": [faculty["id"]],
                     "co_investigators": [], "team_members": []},
        },
    ).json()
    completed = client.post(
        f"{API}/research/projects",
        json={"title": "Quantum Dots", "uploaded_by": "registrar:1",
              "lifecycle_status": "completed",
              "team": {"principal_investigators": [], "co_investigators": [],
                       "team_members": [faculty["id"]]}},
    ).json()
    grant = client.post(
        f"{API}/research/grants",
        json={"title": "SERB Core Grant", "grant_number": "CRG-01",
              "uploaded_by": "registrar:1", "amount": 3000000,
              "links": {"projects": [project["id"]], "funding_agencies": []}},
    ).json()
    student = client.post(
        f"{API}/students",
        json={"name": "Ravi Kumar", "student_type": "phd", "uploaded_by": "registrar:1",
              "roll_number": "PHD-2201",
              "links": {"supervisors": [faculty["id"]]}},
    ).json()
    alum = client.post(
        f"{API}/students",
        json={"name": "Meera Iyer", "student_type": "alumni", "uploaded_by": "registrar:1",
              "roll_number": "MSc-1902",
              "links": {"co_supervisors": [faculty["id"]]}},
    ).json()
    cls = client.post(
        f"{API}/teaching/classes",
        json={"title": "Quantum Mechanics", "uploaded_by": "registrar:1",
              "course_code": "PHY-301", "programme": "BSc Physics", "semester": 3,
              "credits": 4,
              "weekly_schedule": [
                  {"day": "mon", "start": "09:00", "end": "10:30"},
                  {"day": "thu", "start": "14:00", "end": "15:00"}],
              "links": {"teachers": [faculty["id"]]}},
    ).json()
    publication = client.post(
        f"{API}/publications",
        json={"title": "Quantum dots in perovskites", "publication_type": "journal_article",
              "uploaded_by": "registrar:1", "authors": [{"name": "Asha Nair"}],
              "links": {"faculty": [faculty["id"]]}},
    ).json()

    got = client.get(f"{API}/faculty/{faculty['id']}")
    assert got.status_code == 200, got.text
    body = got.json()
    roles = {p["kind"]: p["title"] for p in body["research"]["projects"]}
    assert roles == {"leads": "Perovskite Cells", "works_in": "Quantum Dots"}
    assert [g["title"] for g in body["research"]["grants"]] == ["SERB Core Grant"]
    assert [s["title"] for s in body["supervision"]["current"]] == ["Ravi Kumar"]
    assert [s["title"] for s in body["supervision"]["completed"]] == ["Meera Iyer"]
    assert body["supervision"]["completed"][0]["student_type"] == "alumni"
    teaching = body["teaching"]
    assert teaching["classes"][0]["course_code"] == "PHY-301"
    assert teaching["classes"][0]["weekly_hours"] == 2.5
    assert teaching["total_weekly_hours"] == 2.5
    assert body["stats"] == {
        "publications": 1, "active_projects": 1, "grants": 1,
        "students_supervised": 1, "courses": 1, "committees": 0,
    }
    assert str(project["id"])[0:4] == "obj:" and str(grant["id"])[0:4] == "obj:"
    assert str(student["id"])[0:4] == "obj:" and str(alum["id"])[0:4] == "obj:"
    assert str(cls["id"])[0:4] == "obj:" and str(publication["id"])[0:4] == "obj:" and str(completed["id"])[0:4] == "obj:"


def test_get_missing_is_404(client):
    assert client.get(f"{API}/faculty/obj:faculty:DOESNOTEXIST").status_code == 404


def test_update_merge_and_duplicate_guard(client):
    faculty = _faculty(client).json()
    other = _faculty(client, name="Other", employee_id="EMP-9002", faculty_code=None).json()

    updated = client.put(
        f"{API}/faculty/{faculty['id']}",
        json={"designation": "Professor", "research_interests": ["2D materials"],
              "degrees": [], "uploaded_by": "registrar:2"},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["designation"] == "Professor"
    assert body["research_interests"] == ["2D materials"]
    assert body["degrees"] == []  # section replaced
    # await: untouched fields stay
    assert body["department"] == "Physics"
    assert body["awards"][0]["title"] == "Young Scientist Award"

    conflict = client.put(
        f"{API}/faculty/{other['id']}",
        json={"employee_id": "emp-1001", "uploaded_by": "registrar:2"},
    )
    assert conflict.status_code == 409
    assert client.patch(
        f"{API}/faculty/{faculty['id']}",
        json={"office": "C-101", "uploaded_by": "registrar:2"},
    ).json()["office"] == "C-101"
    assert client.put(
        f"{API}/faculty/obj:faculty:MISSING",
        json={"office": "X", "uploaded_by": "registrar:2"},
    ).status_code == 404


def test_committee_memberships_update_round_trip(client):
    iqac = client.post(f"{API}/objects", json={"object_type": "committee", "title": "IQAC",
                                               "created_by": "registrar:1"}).json()
    naac = client.post(f"{API}/objects", json={"object_type": "committee", "title": "NAAC",
                                               "created_by": "registrar:1"}).json()
    faculty = _faculty(client, links={"committees": [iqac["id"]]}).json()
    updated = client.put(
        f"{API}/faculty/{faculty['id']}",
        json={"links": {"committees": [naac["id"]]}, "uploaded_by": "registrar:2"},
    ).json()
    assert [link["title"] for link in updated["links"]["committees"]] == ["NAAC"]
    got = client.get(f"{API}/faculty/{faculty['id']}").json()
    assert got["stats"]["committees"] == 1
    assert [link["id"] for link in got["links"]["committees"]] == [naac["id"]]


def test_photo_upload_download_replace_and_guards(client, tmp_path):
    faculty = _faculty(client).json()
    # no photo yet -> 404
    assert client.get(f"{API}/faculty/{faculty['id']}/photo").status_code == 404
    # non-image -> 422
    bad = client.put(
        f"{API}/faculty/{faculty['id']}/photo",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert bad.status_code == 422
    attached = client.put(
        f"{API}/faculty/{faculty['id']}/photo?uploaded_by=registrar:1",
        files={"file": ("asha.png", b"\x89PNG-fake-bytes", "image/png")},
    )
    assert attached.status_code == 200, attached.text
    body = attached.json()
    assert body["photo_file_name"] == "asha.png"
    assert body["photo_url"].endswith(f"/api/v1/faculty/{faculty['id']}/photo")
    # photo facts persisted across a fresh fetch
    fetched = client.get(f"{API}/faculty/{faculty['id']}").json()
    assert fetched["photo_file_size"] == len(b"\x89PNG-fake-bytes")
    blob = client.get(f"{API}/faculty/{faculty['id']}/photo")
    assert blob.status_code == 200
    assert blob.content == b"\x89PNG-fake-bytes"
    assert blob.headers["content-type"].startswith("image/png")
    # replace swaps the blob
    client.put(
        f"{API}/faculty/{faculty['id']}/photo",
        files={"file": ("asha2.jpg", b"\xff\xd8new", "image/jpeg")},
    )
    blob2 = client.get(f"{API}/faculty/{faculty['id']}/photo")
    assert blob2.content == b"\xff\xd8new"
    assert blob2.headers["content-type"].startswith("image/jpeg")
    # leftover garbage: photo upload against a missing faculty 404s
    missing = client.put(
        f"{API}/faculty/obj:faculty:MISSING/photo",
        files={"file": ("x.png", b"z", "image/png")},
    )
    assert missing.status_code == 404


def test_delete_then_404(client):
    faculty = _faculty(client).json()
    assert client.delete(f"{API}/faculty/{faculty['id']}").status_code == 204
    assert client.get(f"{API}/faculty/{faculty['id']}").status_code == 404
    assert client.delete(f"{API}/faculty/{faculty['id']}").status_code == 404


def test_events_and_audit_round_trip(client):
    faculty = _faculty(client).json()
    assert faculty["uploaded_by"] == "registrar:1"
    assert faculty["version"] == 1
    assert any("Created" in event for event in faculty["events"])
    updated = client.put(
        f"{API}/faculty/{faculty['id']}",
        json={"notes": "Updated notes.", "uploaded_by": "registrar:2"},
    ).json()
    assert updated["version"] > 1
    assert updated["notes"] == "Updated notes."
    # metadata record exposes the L6 keys (seven-layer auditability)
    assert updated["metadata"]["designation"] == "Associate Professor"
