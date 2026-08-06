"""Integration tests for the Students API (student registry slice).

Mirrors ``test_publications_api.py``: in-memory SQLite (StaticPool) through
the real SQLAlchemy repository adapter, so the full stack — FastAPI routes,
mappers, use cases, domain, persistence — is exercised without PostgreSQL,
disk state, or network.
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

from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.session import get_db
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
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


def _payload(**overrides):
    body = {
        "name": "Asha Verma",
        "student_type": "ug",
        "uploaded_by": "faculty:1",
        "status": "active",
        "roll_number": "BSc-101",
        "registration_number": "REG-101",
        "university_enrollment": "UNIV-2026-101",
        "email": "asha@univ.edu",
        "phone": "9000000001",
        "programme": "BSc Mathematics with Data Science",
        "department": "Mathematics",
        "semester": 1,
        "section": "A",
        "batch": "2026-30",
        "admission_date": "2026-07-15",
        "expected_graduation": "2030-05",
        "tags": ["hostel", "scholarship"],
    }
    body.update(overrides)
    # keep the fixture unique per roll number unless explicitly overridden —
    # the registry legitimately rejects a reused university enrollment (409).
    if "roll_number" in overrides and "university_enrollment" not in overrides:
        body["university_enrollment"] = f"UNIV-{overrides['roll_number']}"
    return body


def test_create_get_update_delete_roundtrip(client):
    created = client.post("/api/v1/students", json=_payload())
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "Asha Verma"
    assert body["roll_number"] == "BSc-101"
    assert body["student_type"] == "ug"
    assert body["semester"] == 1
    assert body["tags"] == ["hostel", "scholarship"]
    assert body["version"] == 1
    sid = body["id"]

    fetched = client.get(f"/api/v1/students/{sid}")
    assert fetched.status_code == 200
    assert fetched.json()["email"] == "asha@univ.edu"
    assert fetched.json()["metadata"]["roll_number"] == "BSc-101"

    updated = client.patch(
        f"/api/v1/students/{sid}",
        json={"semester": 2, "research_area": "Graph ML", "uploaded_by": "faculty:1"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["semester"] == 2
    assert updated.json()["research_area"] == "Graph ML"
    assert updated.json()["roll_number"] == "BSc-101"  # untouched
    assert updated.json()["version"] > body["version"]

    deleted = client.delete(f"/api/v1/students/{sid}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/students/{sid}").status_code == 404


def test_create_duplicate_roll_number_is_409(client):
    assert client.post("/api/v1/students", json=_payload()).status_code == 201
    dup = client.post(
        "/api/v1/students", json=_payload(name="Clone", roll_number="bsc-101")
    )
    assert dup.status_code == 409


def test_create_duplicate_enrollment_is_409(client):
    assert client.post("/api/v1/students", json=_payload()).status_code == 201
    dup = client.post(
        "/api/v1/students",
        json=_payload(name="Other", roll_number="BSc-999",
                      university_enrollment="UNIV-2026-101"),
    )
    assert dup.status_code == 409


def test_create_validation_errors(client):
    assert client.post(
        "/api/v1/students", json=_payload(student_type="kindergarten")
    ).status_code == 422
    assert client.post(
        "/api/v1/students", json=_payload(email="not-an-email")
    ).status_code == 422
    assert client.post(
        "/api/v1/students", json=_payload(roll_number="   ")
    ).status_code == 422
    assert client.post(
        "/api/v1/students", json=_payload(links={"bogus": []})
    ).status_code == 422


def test_list_students_filters_search_and_pagination(client):
    client.post("/api/v1/students", json=_payload(roll_number="101"))
    client.post(
        "/api/v1/students",
        json=_payload(name="Ravi Kumar", roll_number="102", student_type="pg", semester=3),
    )
    client.post(
        "/api/v1/students",
        json=_payload(name="Meena Iyer", roll_number="103", programme="PhD Physics",
                      student_type="phd"),
    )
    listing = client.get("/api/v1/students")
    assert listing.status_code == 200
    assert listing.json()["total_count"] == 3

    assert client.get("/api/v1/students?student_type=pg").json()["total_count"] == 1
    assert client.get("/api/v1/students?semester=3").json()["total_count"] == 1
    assert client.get("/api/v1/students?programme=PhD Physics").json()["total_count"] == 1
    assert client.get("/api/v1/students?q=ravi").json()["total_count"] == 1
    assert client.get("/api/v1/students?q=meena").json()["total_count"] == 1
    page = client.get("/api/v1/students?page=3&page_size=1").json()
    assert page["total_count"] == 3 and len(page["items"]) == 1


def test_student_types_cover_ug_pg_phd_alumni(client):
    for kind in ("ug", "pg", "phd", "alumni"):
        res = client.post(
            "/api/v1/students",
            json=_payload(name=f"S-{kind}", roll_number=f"roll-{kind}", student_type=kind),
        )
        assert res.status_code == 201, res.text
        assert res.json()["student_type"] == kind
    assert client.get("/api/v1/students?student_type=alumni").json()["total_count"] == 1


def test_student_links_to_existing_objects(client):
    faculty = client.post(
        "/api/v1/objects",
        json={"object_type": "faculty", "title": "Dr. Rao", "created_by": "admin"},
    )
    assert faculty.status_code == 201, faculty.text
    fid = faculty.json()["id"]
    project = client.post(
        "/api/v1/objects",
        json={"object_type": "research_project", "title": "Graph ML", "created_by": "admin"},
    )
    pid = project.json()["id"]

    created = client.post(
        "/api/v1/students",
        json=_payload(
            student_type="phd",
            links={"supervisors": [fid], "projects": [pid]},
        ),
    )
    assert created.status_code == 201, created.text
    links = created.json()["links"]
    assert [link["id"] for link in links["supervisors"]] == [fid]
    assert [link["id"] for link in links["projects"]] == [pid]

    # the object lens: students supervised by this faculty member
    lens = client.get(f"/api/v1/students?object_id={fid}")
    assert lens.json()["total_count"] == 1

    # link targets must exist
    bad = client.post(
        "/api/v1/students",
        json=_payload(roll_number="X-1", links={"supervisors": ["obj:faculty:DEADBEEFDEADBEEF"]}),
    )
    assert bad.status_code == 422


def test_update_student_links_merge_semantics(client):
    f1 = client.post("/api/v1/objects", json={
        "object_type": "faculty", "title": "Dr. One", "created_by": "admin"}).json()["id"]
    f2 = client.post("/api/v1/objects", json={
        "object_type": "faculty", "title": "Dr. Two", "created_by": "admin"}).json()["id"]
    f3 = client.post("/api/v1/objects", json={
        "object_type": "faculty", "title": "Dr. Three", "created_by": "admin"}).json()["id"]
    sid = client.post(
        "/api/v1/students",
        json=_payload(links={"supervisors": [f1], "co_supervisors": [f2]}),
    ).json()["id"]
    updated = client.patch(
        f"/api/v1/students/{sid}",
        json={"links": {"supervisors": [f3]}, "uploaded_by": "faculty:1"},
    )
    assert updated.status_code == 200
    links = updated.json()["links"]
    assert [link["id"] for link in links["supervisors"]] == [f3]     # replaced
    assert [link["id"] for link in links["co_supervisors"]] == [f2]  # untouched


def test_import_students_csv_reports_duplicates_and_errors(client):
    text = (
        "Roll No,Name,Email,Section,Programme,Semester\n"
        "101,Asha Verma,asha@univ.edu,A,BSc Mathematics,1\n"
        "102,Ravi Kumar,ravi@univ.edu,A,BSc Mathematics,1\n"
    )
    first = client.post(
        "/api/v1/students/import", json={"text": text, "uploaded_by": "faculty:1"}
    )
    assert first.status_code == 200, first.text
    assert len(first.json()["created"]) == 2

    second = client.post(
        "/api/v1/students/import",
        json={"text": text + "101,Duplicate,d@u.edu,A,BSc,1\n,No Roll,n@u.edu,A,BSc,1\n",
              "uploaded_by": "faculty:1"},
    )
    body = second.json()
    assert body["created"] == []
    assert len(body["skipped_duplicates"]) == 3  # all three existing-by-roll rows
    assert len(body["errors"]) == 1              # the row without a roll number


def test_export_students_csv(client):
    client.post("/api/v1/students/import", json={
        "text": "Roll No,Name,Email\n101,Asha Verma,asha@univ.edu\n",
        "uploaded_by": "faculty:1",
    })
    res = client.get("/api/v1/students/export")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    lines = res.text.strip().split("\n")
    assert lines[0].startswith("Roll No,Name,Email")
    assert "101,Asha Verma,asha@univ.edu" in lines[1]


def test_get_student_404_for_non_student_objects(client):
    course = client.post(
        "/api/v1/objects",
        json={"object_type": "course", "title": "CF", "created_by": "admin"},
    ).json()["id"]
    assert client.get(f"/api/v1/students/{course}").status_code == 404
    assert client.get("/api/v1/students/obj:student:DEADBEEFDEADBEEF").status_code == 404
