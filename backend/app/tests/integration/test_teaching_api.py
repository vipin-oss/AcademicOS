"""Integration tests for the Teaching API (classes → gradebook → reports).

Mirrors ``test_publications_api.py``: in-memory SQLite (StaticPool) plus a
temporary local storage root, exercising routes → mappers → use cases →
domain → SQLAlchemy adapter → FileStorage adapter without PostgreSQL, real
disk state, or network.
"""
from __future__ import annotations
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.object_id import ObjectId
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

from app.api.routes.teaching import get_storage
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
    storage = LocalFileStorage(str(tmp_path / "storage"))

    def _override_db():
        yield session

    def _override_storage():
        return storage

    app.dependency_overrides[get_db] = _override_db
    fake_user = UniversalObject.create(
        object_type=ObjectType.USER,
        title="test.user",
        created_by="system",
        status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:test-user-0001"),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_storage] = _override_storage
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


# --------------------------------------------------------------------------- helpers
def _create_class(client, **overrides):
    body = {
        "title": "Computer Fundamentals",
        "uploaded_by": "faculty:1",
        "status": "active",
        "course_code": "CS-101",
        "programme": "BSc Mathematics with Data Science",
        "semester": 1,
        "section": "A",
        "session": "2026-27",
        "credits": 4.0,
        "weekly_schedule": [{"day": "mon", "start": "09:00", "end": "10:00"}],
        "room": "LH-2",
        "class_mode": "offline",
    }
    body.update(overrides)
    res = client.post("/api/v1/teaching/classes", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _import_students(client, text=None):
    text = text or (
        "Roll No,Name,Email,Section,Programme,Semester\n"
        "101,Asha Verma,asha@univ.edu,A,BSc Mathematics,1\n"
        "102,Ravi Kumar,ravi@univ.edu,A,BSc Mathematics,1\n"
        "103,Meena Iyer,meena@univ.edu,A,BSc Mathematics,1\n"
    )
    res = client.post("/api/v1/students/import", json={"text": text, "uploaded_by": "f:1"})
    assert res.status_code == 200, res.text
    return res.json()["created"]


def _student_ids(client):
    return [s["id"] for s in client.get("/api/v1/students?page_size=100").json()["items"]]


def _enroll_all(client, class_id):
    ids = _student_ids(client)
    res = client.post(
        f"/api/v1/teaching/classes/{class_id}/enroll",
        json={"student_ids": ids, "actor": "faculty:1"},
    )
    assert res.status_code == 200, res.text
    return ids


def _create_assignment(client, class_id, **overrides):
    body = {
        "title": "Assignment 1",
        "uploaded_by": "faculty:1",
        "status": "active",
        "assignment_type": "assignment",
        "max_marks": 20.0,
        "deadline": "2999-01-01",
        "late_allowed": True,
        "weightage": 100.0,
    }
    body.update(overrides)
    res = client.post(f"/api/v1/teaching/classes/{class_id}/assignments", json=body)
    assert res.status_code == 201, res.text
    return res.json()


# --------------------------------------------------------------------------- classes
def test_class_full_lifecycle(client):
    cls = _create_class(client)
    assert cls["student_count"] == 0
    assert cls["weekly_schedule"] == [{"day": "mon", "start": "09:00", "end": "10:00"}]
    cid = cls["id"]

    fetched = client.get(f"/api/v1/teaching/classes/{cid}")
    assert fetched.status_code == 200
    assert fetched.json()["course_code"] == "CS-101"

    listing = client.get("/api/v1/teaching/classes?session=2026-27")
    assert listing.json()["total_count"] == 1
    assert client.get("/api/v1/teaching/classes?q=computer").json()["total_count"] == 1
    assert client.get("/api/v1/teaching/classes?semester=2").json()["total_count"] == 0

    updated = client.patch(
        f"/api/v1/teaching/classes/{cid}",
        json={"room": "LH-9", "uploaded_by": "faculty:1"},
    )
    assert updated.status_code == 200
    assert updated.json()["room"] == "LH-9"
    assert updated.json()["session"] == "2026-27"

    removed = client.delete(f"/api/v1/teaching/classes/{cid}")
    assert removed.status_code == 200
    assert removed.json()["assignments"] == 0
    assert client.get(f"/api/v1/teaching/classes/{cid}").status_code == 404


def test_class_validation_and_404s(client):
    bad_mode = client.post("/api/v1/teaching/classes", json={
        "title": "X", "uploaded_by": "f", "class_mode": "hybrid-ish"})
    assert bad_mode.status_code == 422
    bad_schedule = client.post("/api/v1/teaching/classes", json={
        "title": "X", "uploaded_by": "f",
        "weekly_schedule": [{"day": "funday", "start": "09:00"}]})
    assert bad_schedule.status_code == 422
    assert client.get("/api/v1/teaching/classes/obj:course:DEADBEEFDEADBEEF").status_code == 404


def test_class_teacher_links_via_objects(client):
    faculty = client.post("/api/v1/objects", json={
        "object_type": "faculty", "title": "Dr. Rao", "created_by": "admin"}).json()["id"]
    cls = _create_class(client, links={"teachers": [faculty]})
    assert [link["id"] for link in cls["links"]["teachers"]] == [faculty]
    # faculty lens: classes this faculty member teaches
    lens = client.get(f"/api/v1/teaching/classes?object_id={faculty}")
    assert lens.json()["total_count"] == 1


# --------------------------------------------------------------------------- enrollment
def test_enrollment_flow_manual_csv_and_roster(client):
    cls = _create_class(client)
    _import_students(client)
    ids = _enroll_all(client, cls["id"])
    assert len(ids) == 3

    roster = client.get(f"/api/v1/teaching/classes/{cls['id']}/roster")
    assert roster.status_code == 200
    assert [r["roll_number"] for r in roster.json()] == ["101", "102", "103"]

    fetched = client.get(f"/api/v1/teaching/classes/{cls['id']}")
    assert fetched.json()["student_count"] == 3

    # idempotent re-enroll
    again = client.post(
        f"/api/v1/teaching/classes/{cls['id']}/enroll",
        json={"student_ids": [ids[0]], "actor": "faculty:1"},
    )
    assert again.json()["already_enrolled"] == [ids[0]]

    # unenroll one student
    removed = client.delete(f"/api/v1/teaching/classes/{cls['id']}/enroll/{ids[2]}")
    assert removed.status_code == 204
    roster = client.get(f"/api/v1/teaching/classes/{cls['id']}/roster").json()
    assert [r["roll_number"] for r in roster] == ["101", "102"]

    # CSV enrollment resolves roll numbers
    csv_res = client.post(
        f"/api/v1/teaching/classes/{cls['id']}/enroll/csv",
        json={"text": "Roll No\n103\n999\n", "actor": "faculty:1"},
    )
    assert csv_res.status_code == 200
    body = csv_res.json()
    assert len(body["enrolled"]) == 1
    assert len(body["errors"]) == 1  # roll 999 unknown

    # student lens: classes this student is enrolled in
    lens = client.get(f"/api/v1/teaching/classes?object_id={ids[0]}")
    assert lens.json()["total_count"] == 1


# --------------------------------------------------------------------------- assignments + files
def test_assignment_lifecycle_with_attachment(client):
    cls = _create_class(client)
    assignment = _create_assignment(
        client, cls["id"],
        rubric=[{"criterion": "Correctness", "marks": 15}, {"criterion": "Style", "marks": 5}],
    )
    assert assignment["class_title"] == "Computer Fundamentals"
    assert assignment["rubric"][0]["criterion"] == "Correctness"
    aid = assignment["id"]

    listing = client.get(f"/api/v1/teaching/classes/{cls['id']}/assignments")
    assert listing.json()["total_count"] == 1
    lens = client.get(f"/api/v1/teaching/assignments?object_id={cls['id']}")
    assert lens.json()["total_count"] == 1

    # attachment round-trip
    attached = client.put(
        f"/api/v1/teaching/assignments/{aid}/attachment",
        files={"file": ("questions.pdf", io.BytesIO(b"pdf-body"), "application/pdf")},
    )
    assert attached.status_code == 200, attached.text
    assert attached.json()["attachment_file_name"] == "questions.pdf"
    assert attached.json()["attachment_file_size"] == 8
    assert attached.json()["attachment_url"].endswith(f"/teaching/assignments/{aid}/attachment")

    downloaded = client.get(f"/api/v1/teaching/assignments/{aid}/attachment")
    assert downloaded.status_code == 200
    assert downloaded.content == b"pdf-body"

    updated = client.patch(
        f"/api/v1/teaching/assignments/{aid}",
        json={"max_marks": 30.0, "uploaded_by": "faculty:1"},
    )
    assert updated.json()["max_marks"] == 30.0

    removed = client.delete(f"/api/v1/teaching/assignments/{aid}")
    assert removed.status_code == 200
    assert client.get(f"/api/v1/teaching/assignments/{aid}").status_code == 404
    gone = client.get(f"/api/v1/teaching/assignments/{aid}/attachment")
    assert gone.status_code == 404


def test_assignment_validation(client):
    cls = _create_class(client)
    bad = client.post(f"/api/v1/teaching/classes/{cls['id']}/assignments", json={
        "title": "X", "uploaded_by": "f", "assignment_type": "homework"})
    assert bad.status_code == 422
    ghost = client.post("/api/v1/teaching/classes/obj:course:DEADBEEFDEADBEEF/assignments",
                        json={"title": "X", "uploaded_by": "f"})
    assert ghost.status_code == 404


# --------------------------------------------------------------------------- submissions + marks
def test_submission_flow_file_download_grade_and_grid(client):
    cls = _create_class(client)
    _import_students(client)
    ids = _enroll_all(client, cls["id"])
    assignment = _create_assignment(client, cls["id"])

    # on-time submission with file + comments (multipart, like the browser)
    submitted = client.post(
        f"/api/v1/teaching/assignments/{assignment['id']}/submit",
        data={"student_id": ids[0], "comments": "Please review Q3.", "actor": "student:101"},
        files={"file": ("answer.pdf", io.BytesIO(b"my-answers"), "application/pdf")},
    )
    assert submitted.status_code == 201, submitted.text
    body = submitted.json()
    assert body["student_roll"] == "101"
    assert body["is_late"] is False
    assert body["file_url"].endswith(f"/teaching/submissions/{body['id']}/file")
    sub_id = body["id"]

    downloaded = client.get(f"/api/v1/teaching/submissions/{sub_id}/file")
    assert downloaded.status_code == 200
    assert downloaded.content == b"my-answers"

    # resubmit: same object, higher version (version history)
    resub = client.post(
        f"/api/v1/teaching/assignments/{assignment['id']}/submit",
        data={"student_id": ids[0]},
        files={"file": ("answer-v2.pdf", io.BytesIO(b"v2"), "application/pdf")},
    )
    assert resub.status_code == 201
    assert resub.json()["id"] == sub_id
    assert resub.json()["version"] > body["version"]

    # grade above max -> 422; valid grade -> 200
    too_high = client.put(
        f"/api/v1/teaching/submissions/{sub_id}/grade",
        json={"marks": 25.0, "actor": "faculty:1"},
    )
    assert too_high.status_code == 422
    graded = client.put(
        f"/api/v1/teaching/submissions/{sub_id}/grade",
        json={"marks": 18.0, "faculty_feedback": "Great work", "actor": "faculty:1"},
    )
    assert graded.status_code == 200
    assert graded.json()["marks"] == 18.0
    assert graded.json()["graded_by"] == "faculty:1"

    # grid: one graded, two pending
    grid = client.get(f"/api/v1/teaching/assignments/{assignment['id']}/grid")
    assert grid.status_code == 200
    grid_body = grid.json()
    assert (grid_body["submitted_count"], grid_body["pending_count"],
            grid_body["graded_count"]) == (0, 2, 1)
    states = {r["student_roll"]: r["state"] for r in grid_body["rows"]}
    assert states == {"101": "graded", "102": "pending", "103": "pending"}

    # submissions lenses
    by_assignment = client.get(
        f"/api/v1/teaching/submissions?assignment_id={assignment['id']}")
    assert by_assignment.json()["total_count"] == 1
    by_student = client.get(f"/api/v1/teaching/submissions?student_id={ids[0]}")
    assert by_student.json()["total_count"] == 1
    graded_only = client.get(
        f"/api/v1/teaching/submissions?assignment_id={assignment['id']}&state=graded")
    assert graded_only.json()["total_count"] == 1


def test_late_submission_rules(client):
    cls = _create_class(client)
    _import_students(client)
    ids = _enroll_all(client, cls["id"])

    allowed = _create_assignment(
        client, cls["id"], title="Late OK", deadline="2020-01-01", late_allowed=True)
    late = client.post(
        f"/api/v1/teaching/assignments/{allowed['id']}/submit",
        data={"student_id": ids[0]},
    )
    assert late.status_code == 201
    assert late.json()["is_late"] is True

    forbidden = _create_assignment(
        client, cls["id"], title="No Late", deadline="2020-01-01", late_allowed=False)
    rejected = client.post(
        f"/api/v1/teaching/assignments/{forbidden['id']}/submit",
        data={"student_id": ids[0]},
    )
    assert rejected.status_code == 422

    # faculty can back-date an on-time submission
    backdated = client.post(
        f"/api/v1/teaching/assignments/{forbidden['id']}/submit",
        data={"student_id": ids[0], "submitted_at": "2019-12-15T10:00:00+00:00"},
    )
    assert backdated.status_code == 201
    assert backdated.json()["is_late"] is False


def test_marks_csv_import_google_forms_loop(client):
    """PART G: assignment lives in AcademicOS; responses come back as CSV."""
    cls = _create_class(client)
    _import_students(client)
    _enroll_all(client, cls["id"])
    form_assignment = _create_assignment(client, cls["id"], title="Google Form Quiz",
                                         assignment_type="quiz", max_marks=10.0)

    csv_text = (
        "Roll No,Marks,Feedback\n"
        "101,9,Well done\n"
        "102,7,\n"
        "103,12,\n"   # above max -> row error
        "999,5,\n"    # unknown roll -> row error
    )
    result = client.post(
        f"/api/v1/teaching/assignments/{form_assignment['id']}/marks/import",
        json={"text": csv_text, "actor": "faculty:1"},
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert len(body["graded"]) == 2
    assert len(body["created_submissions"]) == 2  # created on the fly
    assert len(body["errors"]) == 2

    grid = client.get(f"/api/v1/teaching/assignments/{form_assignment['id']}/grid").json()
    states = {r["student_roll"]: r["state"] for r in grid["rows"]}
    assert states["101"] == "graded" and states["102"] == "graded"
    assert states["103"] == "pending"
    marks = {r["student_roll"]: (r["submission"] or {}).get("marks") for r in grid["rows"]}
    assert marks["101"] == 9.0


# --------------------------------------------------------------------------- attendance
def test_attendance_manual_csv_summary(client):
    cls = _create_class(client)
    _import_students(client)
    ids = _enroll_all(client, cls["id"])
    roll_by_id = {s["id"]: s["roll_number"] for s in
                  client.get("/api/v1/students?page_size=100").json()["items"]}

    day1 = client.post(
        f"/api/v1/teaching/classes/{cls['id']}/attendance",
        json={"session_date": "2026-08-03",
              "records": {ids[0]: "present", ids[1]: "absent", ids[2]: "medical_leave"},
              "actor": "faculty:1"},
    )
    assert day1.status_code == 201, day1.text
    session_id = day1.json()["id"]

    # upsert: same (class, date) updates the SAME session object
    day1_again = client.post(
        f"/api/v1/teaching/classes/{cls['id']}/attendance",
        json={"session_date": "2026-08-03",
              "records": {ids[0]: "late", ids[1]: "present", ids[2]: "present"},
              "actor": "faculty:1"},
    )
    assert day1_again.json()["id"] == session_id

    # CSV import for day 2
    imported = client.post(
        f"/api/v1/teaching/classes/{cls['id']}/attendance/import",
        json={"session_date": "2026-08-04",
              "text": "Roll No,Status\n101,P\n102,A\n999,P\n",
              "actor": "faculty:1"},
    )
    assert imported.status_code == 200
    assert len(imported.json()["applied"]) == 2
    assert len(imported.json()["unknown"]) == 1

    sessions = client.get(f"/api/v1/teaching/classes/{cls['id']}/attendance")
    assert len(sessions.json()) == 2

    summary = client.get(f"/api/v1/teaching/classes/{cls['id']}/attendance/summary")
    assert summary.status_code == 200
    rows = {r["student_roll"]: r for r in summary.json()["rows"]}
    assert rows["101"]["present"] == 1 and rows["101"]["late"] == 1
    assert rows["101"]["percentage"] == 100.0
    assert rows["102"]["percentage"] == 50.0
    assert rows["102"]["below_threshold"] is True        # below 75%
    # day-1 upsert corrected 103 to present; day-2 CSV has no record -> absent
    assert rows["103"]["present"] == 1
    assert rows["103"]["absent"] == 1

    # invalid state / non-enrolled id / bad date -> 422
    assert client.post(
        f"/api/v1/teaching/classes/{cls['id']}/attendance",
        json={"session_date": "2026-08-05", "records": {ids[0]: "sleeping"}},
    ).status_code == 422
    assert client.post(
        f"/api/v1/teaching/classes/{cls['id']}/attendance",
        json={"session_date": "05-08-2026", "records": {ids[0]: "present"}},
    ).status_code == 422
    _ = roll_by_id


# --------------------------------------------------------------------------- gradebook / report / dashboard
def test_gradebook_report_and_export(client):
    cls = _create_class(client)
    _import_students(client)
    ids = _enroll_all(client, cls["id"])
    a1 = _create_assignment(client, cls["id"], title="A1", max_marks=20.0, weightage=50.0,
                            assignment_type="assignment")
    q1 = _create_assignment(client, cls["id"], title="Quiz", max_marks=10.0, weightage=50.0,
                            assignment_type="quiz")

    marks_a1 = "Roll No,Marks\n101,18\n102,5\n103,15\n"
    marks_q1 = "Roll No,Marks\n101,9\n102,4\n"
    for assignment, csv_text in ((a1, marks_a1), (q1, marks_q1)):
        res = client.post(
            f"/api/v1/teaching/assignments/{assignment['id']}/marks/import",
            json={"text": csv_text, "actor": "faculty:1"},
        )
        assert res.status_code == 200, res.text

    book = client.get(f"/api/v1/teaching/classes/{cls['id']}/gradebook")
    assert book.status_code == 200
    book = book.json()
    rows = {r["student_roll"]: r for r in book["rows"]}
    assert rows["101"]["average_percent"] == 90.0       # (90*50 + 90*50)/100
    assert rows["101"]["grade"] == "A+"
    assert rows["103"]["cells"][0]["marks"] == 15.0
    assert rows["103"]["cells"][1]["marks"] is None     # not graded -> blank cell
    assert len(book["assignments"]) == 2

    exported = client.get(f"/api/v1/teaching/classes/{cls['id']}/gradebook/export")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    lines = exported.text.strip().split("\n")
    assert lines[0].endswith("Internal %,Grade")

    report = client.get(f"/api/v1/teaching/classes/{cls['id']}/report")
    assert report.status_code == 200
    report = report.json()
    assert report["class_info"]["title"] == "Computer Fundamentals"
    assert len(report["roster"]) == 3
    assert report["late_submissions"] == 0
    assert report["average_marks_percent"] is not None
    assert isinstance(report["weak_students"], list)
    assert any(t["roll_number"] == "101" for t in report["top_performers"])
    assert any(w["roll_number"] == "102" for w in report["weak_students"])  # 32.5% avg
    assert "gradebook" in report and "attendance" in report
    _ = ids


def test_teaching_dashboard_endpoint(client):
    cls = _create_class(client)
    _import_students(client)
    _enroll_all(client, cls["id"])
    a1 = _create_assignment(client, cls["id"], max_marks=100.0, weightage=100.0)
    res = client.post(
        f"/api/v1/teaching/assignments/{a1['id']}/marks/import",
        json={"text": "Roll No,Marks\n101,95\n102,35\n103,55\n", "actor": "faculty:1"},
    )
    assert res.status_code == 200

    dashboard = client.get("/api/v1/teaching/dashboard")
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["class_count"] == 1
    assert body["student_count"] == 3
    assert body["assignment_count"] == 1
    assert body["graded_submissions"] == 3
    assert body["pending_submissions"] == 0
    assert body["average_marks_percent"] is not None
    assert [t["roll_number"] for t in body["top_performers"]] == ["101"]
    assert any(w["roll_number"] == "102" for w in body["weak_students"])
    assert body["classes"][0]["student_count"] == 3


def test_delete_class_cascades_through_api(client):
    cls = _create_class(client)
    _import_students(client)
    ids = _enroll_all(client, cls["id"])
    assignment = _create_assignment(client, cls["id"])
    client.post(
        f"/api/v1/teaching/assignments/{assignment['id']}/submit",
        data={"student_id": ids[0]},
        files={"file": ("a.pdf", io.BytesIO(b"x"), "application/pdf")},
    )
    client.post(
        f"/api/v1/teaching/classes/{cls['id']}/attendance",
        json={"session_date": "2026-08-03", "records": {ids[0]: "present"}},
    )
    removed = client.delete(f"/api/v1/teaching/classes/{cls['id']}")
    assert removed.status_code == 200
    body = removed.json()
    assert body["assignments"] == 1
    assert body["submissions"] == 1
    assert body["attendance_sessions"] == 1
    assert body["unenrolled_students"] == 3
    assert client.get(f"/api/v1/teaching/classes/{cls['id']}").status_code == 404
    assert client.get(
        f"/api/v1/teaching/classes?object_id={ids[0]}").json()["total_count"] == 0
    # students survive the cleanup
    assert client.get("/api/v1/students").json()["total_count"] == 3
