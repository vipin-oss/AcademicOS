"""Integration tests for the Research API (Projects & Grants slice).

Mirrors ``test_students_api.py``: in-memory SQLite (StaticPool) through the
real SQLAlchemy repository adapter, so the full stack — FastAPI routes,
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


API = "/api/v1"


def _agency(client, name="DST", **overrides):
    body = {"name": name, "uploaded_by": "faculty:1", "status": "active",
            "scheme": "Core Research Grant", "website": "https://dst.gov.in",
            "contact_email": "help@dst.gov.in"}
    body.update(overrides)
    return client.post(f"{API}/research/agencies", json=body)


def _project(client, **overrides):
    body = {
        "title": "Quantum Materials Discovery",
        "uploaded_by": "faculty:1",
        "status": "active",
        "lifecycle_status": "draft",
        "project_code": "DST-2026-0137",
        "department": "Physics",
        "start_date": "2026-04-01",
        "end_date": "2029-03-31",
        "duration": "36 months",
        "budget_approved": 4500000.0,
        "budget_utilized": 0.0,
        "objectives": "Discover qubit-grade materials",
        "keywords": ["quantum", "materials"],
        "priority": "high",
        "tags": ["flagship"],
    }
    body.update(overrides)
    return client.post(f"{API}/research/projects", json=body)


def _grant(client, **overrides):
    body = {
        "title": "Core Research Grant",
        "grant_number": "CRG/2026/004501",
        "uploaded_by": "faculty:1",
        "status": "active",
        "amount": 2400000.0,
        "release_schedule": "annual",
    }
    body.update(overrides)
    return client.post(f"{API}/research/grants", json=body)


def _faculty(client, name):
    resp = client.post(
        f"{API}/objects",
        json={"object_type": "faculty", "title": name, "created_by": "faculty:1"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Agencies
# ---------------------------------------------------------------------------
def test_agency_crud_and_duplicate_409(client):
    created = _agency(client)
    assert created.status_code == 201
    agency = created.json()
    assert agency["name"] == "DST" and agency["scheme"] == "Core Research Grant"

    duplicate = _agency(client, name="dst")
    assert duplicate.status_code == 409
    assert "Duplicate funding agency" in duplicate.json()["detail"]

    listed = client.get(f"{API}/research/agencies", params={"q": "research grant"})
    assert listed.status_code == 200 and listed.json()["total_count"] == 1

    updated = client.patch(f"{API}/research/agencies/{agency['id']}", json={"scheme": "TARE"})
    assert updated.status_code == 200 and updated.json()["scheme"] == "TARE"

    deleted = client.delete(f"{API}/research/agencies/{agency['id']}")
    assert deleted.status_code == 204
    assert client.get(f"{API}/research/agencies/{agency['id']}").status_code == 404


def test_agency_validation_errors(client):
    assert _agency(client, name="  ").status_code == 422
    bad = _agency(client, name="CSIR", website="not-a-url")
    assert bad.status_code == 422


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
def test_project_crud_lifecycle_and_duplicate_code(client):
    created = _project(client)
    assert created.status_code == 201
    project = created.json()
    assert project["lifecycle_status"] == "draft"
    assert project["budget_approved"] == 4500000.0
    assert project["keywords"] == ["quantum", "materials"]

    assert _project(client).status_code == 409  # same project_code

    patched = client.patch(
        f"{API}/research/projects/{project['id']}",
        json={"lifecycle_status": "funded", "budget_utilized": 125000.0},
    )
    assert patched.status_code == 200
    assert patched.json()["lifecycle_status"] == "funded"
    assert patched.json()["budget"]["remaining"] == 4500000.0 - 125000.0

    fetched = client.get(f"{API}/research/projects/{project['id']}")
    assert fetched.status_code == 200 and fetched.json()["project_code"] == "DST-2026-0137"

    assert client.patch(
        f"{API}/research/projects/{project['id']}", json={"lifecycle_status": "bogus"}
    ).status_code == 422

    assert client.delete(f"{API}/research/projects/{project['id']}").status_code == 204
    assert client.get(f"{API}/research/projects/{project['id']}").status_code == 404


def test_project_team_links_are_reverse_visible(client):
    pi = _faculty(client, "Dr Meera Krishnan")
    member = _faculty(client, "Dr Arjun Rao")
    created = _project(
        client,
        team={"principal_investigators": [pi], "team_members": [member]},
    )
    assert created.status_code == 201
    project = created.json()
    assert project["team"]["principal_investigators"][0]["title"] == "Dr Meera Krishnan"
    assert project["team"]["team_members"][0]["title"] == "Dr Arjun Rao"

    # Team replacement (merge semantics: present group only)
    replaced = client.patch(
        f"{API}/research/projects/{project['id']}",
        json={"team": {"principal_investigators": [member]}},
    )
    assert replaced.status_code == 200
    assert [p["title"] for p in replaced.json()["team"]["principal_investigators"]] == ["Dr Arjun Rao"]
    assert [p["title"] for p in replaced.json()["team"]["team_members"]] == ["Dr Arjun Rao"]

    # PI filter (PART 9) resolves through team edges
    by_pi = client.get(f"{API}/research/projects", params={"pi": "arjun"})
    assert by_pi.json()["total_count"] == 1


def test_project_agency_link_and_part9_filters(client):
    agency = _agency(client, name="SERB").json()
    first = _project(client, links={"agencies": [agency["id"]]}, lifecycle_status="active").json()
    _project(client, title="Wetland Ecology Survey", project_code="UGC-9",
             lifecycle_status="completed", department="Botany", start_date="2024-06-01")

    assert client.get(f"{API}/research/projects", params={"status": "active"}).json()["total_count"] == 1
    assert client.get(f"{API}/research/projects", params={"year": 2024}).json()["total_count"] == 1
    assert client.get(f"{API}/research/projects", params={"department": "botany"}).json()["total_count"] == 1
    assert client.get(f"{API}/research/projects", params={"agency": "serb"}).json()["total_count"] == 1
    assert client.get(f"{API}/research/projects", params={"q": "wetland"}).json()["total_count"] == 1
    assert first["links"]["agencies"][0]["object_type"] == "funding_agency"


def test_project_object_lens(client):
    agency = _agency(client, name="AICTE").json()
    project = _project(client, links={"agencies": [agency["id"]]}).json()
    by_lens = client.get(f"{API}/research/projects", params={"object_id": agency["id"]})
    assert by_lens.status_code == 200
    assert [p["id"] for p in by_lens.json()["items"]] == [project["id"]]


# ---------------------------------------------------------------------------
# Timeline (milestones + progress updates)
# ---------------------------------------------------------------------------
def test_milestone_flow(client):
    project = _project(client).json()
    added = client.post(
        f"{API}/research/projects/{project['id']}/milestones",
        json={"title": "Literature review", "date": "2026-06-30"},
    )
    assert added.status_code == 201
    milestone = added.json()
    assert milestone["status"] == "pending"

    fetched = client.get(f"{API}/research/projects/{project['id']}").json()
    assert [m["title"] for m in fetched["milestones"]] == ["Literature review"]

    patched = client.patch(
        f"{API}/research/milestones/{milestone['id']}", json={"status": "done"}
    )
    assert patched.status_code == 200 and patched.json()["status"] == "done"

    assert client.delete(f"{API}/research/milestones/{milestone['id']}").status_code == 204
    assert client.get(f"{API}/research/projects/{project['id']}").json()["milestones"] == []


def test_milestone_validation_errors(client):
    project = _project(client).json()
    assert client.post(
        f"{API}/research/projects/{project['id']}/milestones",
        json={"title": "X", "date": "30-06-2026"},
    ).status_code == 422
    assert client.post(
        f"{API}/research/projects/{project['id']}/milestones",
        json={"title": "", "date": "2026-06-30"},
    ).status_code == 422


def test_progress_update_flow(client):
    project = _project(client).json()
    resp = client.post(
        f"{API}/research/projects/{project['id']}/updates",
        json={"date": "2026-07-01", "percent": 35, "remark": "Setup complete"},
    )
    assert resp.status_code == 200
    updates = resp.json()["progress_updates"]
    assert updates == [{"date": "2026-07-01", "percent": 35.0, "remark": "Setup complete"}]

    assert client.post(
        f"{API}/research/projects/{project['id']}/updates",
        json={"date": "2026-07-02", "percent": 120, "remark": "X"},
    ).status_code == 422


# ---------------------------------------------------------------------------
# Grants + budget tracking
# ---------------------------------------------------------------------------
def test_grant_flow_with_budget_guards(client):
    project = _project(client).json()
    agency = _agency(client, name="SERB").json()
    created = _grant(
        client,
        amount=1000.0,
        links={"projects": [project["id"]], "funding_agencies": [agency["id"]]},
    )
    assert created.status_code == 201
    grant = created.json()
    assert grant["links"]["projects"][0]["id"] == project["id"]

    # Duplicate grant number -> 409
    assert _grant(client).status_code == 409

    inst1 = client.post(
        f"{API}/research/grants/{grant['id']}/installments",
        json={"installment_no": 1, "date": "2026-04-10", "amount": 400.0},
    )
    assert inst1.status_code == 201
    inst2 = client.post(
        f"{API}/research/grants/{grant['id']}/installments",
        json={"installment_no": 2, "date": "2026-10-10", "amount": 600.0, "status": "scheduled"},
    )
    assert inst2.status_code == 201

    exp = client.post(
        f"{API}/research/grants/{grant['id']}/expenditures",
        json={"date": "2026-05-01", "head": "Equipment", "amount": 250.0, "reference": "PO-17"},
    )
    assert exp.status_code == 201

    fetched = client.get(f"{API}/research/grants/{grant['id']}").json()
    assert fetched["budget"] == {"approved": 1000.0, "released": 400.0, "utilized": 250.0, "remaining": 750.0}
    assert [i["installment_no"] for i in fetched["installments"]] == [1, 2]

    # Over-expenditure guard: 800 more would exceed the 1000 sanction.
    over = client.post(
        f"{API}/research/grants/{grant['id']}/expenditures",
        json={"date": "2026-06-01", "head": "Travel", "amount": 800.0},
    )
    assert over.status_code == 422
    assert "remaining balance" in over.json()["detail"]

    # Over-release guard: released (400) + 601 would exceed the sanction.
    assert client.post(
        f"{API}/research/grants/{grant['id']}/installments",
        json={"installment_no": 3, "date": "2026-11-01", "amount": 601.0},
    ).status_code == 422

    # Correction path: delete the installment, budget recomputes.
    assert client.delete(f"{API}/research/installments/{inst2.json()['id']}").status_code == 204
    assert client.delete(f"{API}/research/expenditures/{exp.json()['id']}").status_code == 204
    refetched = client.get(f"{API}/research/grants/{grant['id']}").json()
    assert refetched["budget"]["utilized"] == 0.0
    assert refetched["budget"]["remaining"] == 1000.0


def test_grant_lenses_and_project_budget_reactivity(client):
    project = _project(client).json()
    agency = _agency(client, name="ICMR").json()
    grant = _grant(
        client,
        links={"projects": [project["id"]], "funding_agencies": [agency["id"]]},
    ).json()

    by_project = client.get(f"{API}/research/grants", params={"project_id": project["id"]})
    assert [g["grant_number"] for g in by_project.json()["items"]] == ["CRG/2026/004501"]
    by_agency = client.get(f"{API}/research/grants", params={"agency_id": agency["id"]})
    assert by_agency.json()["total_count"] == 1
    by_q = client.get(f"{API}/research/grants", params={"q": "core research"})
    assert by_q.json()["total_count"] == 1

    # Project workspace budget reflects released installments across grants.
    client.post(
        f"{API}/research/grants/{grant['id']}/installments",
        json={"installment_no": 1, "date": "2026-04-10", "amount": 800000.0},
    )
    workspace = client.get(f"{API}/research/projects/{project['id']}").json()
    assert workspace["budget"]["grants_released"] == 800000.0


def test_grant_delete_cascades_children(client):
    grant = _grant(client).json()
    inst = client.post(
        f"{API}/research/grants/{grant['id']}/installments",
        json={"installment_no": 1, "date": "2026-04-10", "amount": 100.0},
    ).json()
    assert client.delete(f"{API}/research/grants/{grant['id']}").status_code == 204
    assert client.get(f"{API}/research/grants/{grant['id']}").status_code == 404
    assert client.delete(f"{API}/research/installments/{inst['id']}").status_code == 404


# ---------------------------------------------------------------------------
# Dashboard + 404s
# ---------------------------------------------------------------------------
def test_dashboard_cards_and_deadlines(client):
    project = _project(client, lifecycle_status="active").json()
    _project(client, title="P2", project_code="C-2", lifecycle_status="completed",
             budget_approved=None, budget_utilized=None)
    _grant(client)
    client.post(
        f"{API}/research/projects/{project['id']}/milestones",
        json={"title": "Progress report due", "date": "2026-09-30"},
    )

    dash = client.get(f"{API}/research/dashboard").json()
    assert dash["total_projects"] == 2
    assert dash["active_projects"] == 1
    assert dash["completed_projects"] == 1
    assert dash["total_grants"] == 1
    assert dash["budget_approved"] == 4500000.0
    assert dash["upcoming_deadlines"][0]["title"] == "Progress report due"
    assert dash["upcoming_deadlines"][0]["project_title"] == "Quantum Materials Discovery"


def test_unknown_ids_404(client):
    fake = "obj:research_project:NOPE000000000000"
    assert client.get(f"{API}/research/projects/{fake}").status_code == 404
    assert client.get(f"{API}/research/grants/obj:grant:NOPE000000000000").status_code == 404
    assert client.get(
        f"{API}/research/agencies/obj:funding_agency:NOPE000000000000"
    ).status_code == 404
    assert client.delete(f"{API}/research/milestones/obj:project_milestone:NOPE000000000000").status_code == 404
