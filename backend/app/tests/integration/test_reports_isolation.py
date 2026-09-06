"""Multi-user isolation regression tests for the Reports & Analytics module.

2026-09 security hardening (Phase 1). Before this fix, every report use
case except Academic CV constructed ``Snapshot(repository)`` with no
owner scope at all, so ``GET /reports/*`` for any authenticated user
returned every user's publications, events, projects, students, finance
records, etc. — an indirect cross-user leak reachable through the
dashboard, every per-module report, the generic CSV/PDF/XLSX export
endpoint, and (via one further bug found in the same pass) even the
Academic CV export when routed through the generic exporter rather than
its own dedicated endpoint.

This file proves the fix with two real, distinct users and real HTTP
requests — not just that the use case *accepts* an owner_user_id
parameter, but that the whole chain (route -> mapper -> query -> use
case -> Snapshot -> repository) actually enforces it, and that it does
not regress the legitimate same-user case (a user must still see their
own data).
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

from app.api.dependencies.auth import get_current_user
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.value_objects.object_id import ObjectId
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories.sqlalchemy_object_repository import (
    SQLAlchemyObjectRepository,
)
from app.main import app

API = "/api/v1"


@pytest.fixture()
def harness():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()

    def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db

    user_a = UniversalObject.create(
        object_type=ObjectType.USER, title="Alice", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:reports-alice-0001"),
    )
    user_b = UniversalObject.create(
        object_type=ObjectType.USER, title="Bob", created_by="system",
        status=ObjectStatus.ACTIVE, object_id=ObjectId("obj:user:reports-bob-0001"),
    )
    current = {"user": user_a}
    app.dependency_overrides[get_current_user] = lambda: current["user"]

    repo = SQLAlchemyObjectRepository(session)

    def _seed(owner: UniversalObject, suffix: str):
        """One of each report-relevant record type, owned by ``owner``."""
        pub = UniversalObject.create(
            ObjectType.PUBLICATION, f"{owner.title}'s private paper {suffix}",
            created_by=str(owner.id), status=ObjectStatus.ACTIVE,
            object_id=ObjectId(f"obj:publication:rep-{suffix}"),
        )
        pub.pop_domain_events()
        repo.save(pub)

        project = UniversalObject.create(
            ObjectType.RESEARCH_PROJECT, f"{owner.title}'s private project {suffix}",
            created_by=str(owner.id), status=ObjectStatus.ACTIVE,
            object_id=ObjectId(f"obj:research_project:rep-{suffix}"),
        )
        project.pop_domain_events()
        repo.save(project)

        event = UniversalObject.create(
            ObjectType.EVENT, f"{owner.title}'s private event {suffix}",
            created_by=str(owner.id), status=ObjectStatus.ACTIVE,
            object_id=ObjectId(f"obj:event:rep-{suffix}"),
        )
        event.pop_domain_events()
        repo.save(event)
        session.commit()

    _seed(user_a, "a")
    _seed(user_b, "b")

    with TestClient(app) as c:
        yield c, current, user_a, user_b

    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _as(current, user):
    current["user"] = user


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
def test_dashboard_counts_only_the_callers_own_records(harness):
    client, current, user_a, user_b = harness

    _as(current, user_a)
    dash_a = client.get(f"{API}/reports/dashboard").json()
    assert dash_a["total_publications"] == 1
    assert dash_a["total_projects"] == 1
    assert dash_a["total_events"] == 1

    _as(current, user_b)
    dash_b = client.get(f"{API}/reports/dashboard").json()
    assert dash_b["total_publications"] == 1
    assert dash_b["total_projects"] == 1
    assert dash_b["total_events"] == 1
    # Neither total ever reflects BOTH users' records combined (would be 2).


# ---------------------------------------------------------------------------
# Per-module reports (publications / research / events) never cross users
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "path,title_field",
    [
        ("publications", "Alice's private paper a"),
        ("research", "Alice's private project a"),
    ],
)
def test_per_module_report_never_shows_other_users_titles(harness, path, title_field):
    client, current, user_a, user_b = harness

    _as(current, user_b)
    resp_b = client.get(f"{API}/reports/{path}")
    assert resp_b.status_code == 200, resp_b.text
    body_b = resp_b.text
    assert "Alice" not in body_b, f"user B's {path} report leaked user A's data: {body_b[:400]}"

    _as(current, user_a)
    resp_a = client.get(f"{API}/reports/{path}")
    assert resp_a.status_code == 200, resp_a.text
    assert "Alice" in resp_a.text, f"legitimate same-user {path} report regressed — user A can't see their own data"


def test_events_report_counts_only_the_callers_own_event(harness):
    """The events report surfaces counts/charts, not per-item titles, so
    isolation is proven by count rather than by title text: each user
    must see exactly their own 1 event, never both users' 2."""
    client, current, user_a, user_b = harness

    for user in (user_a, user_b):
        _as(current, user)
        resp = client.get(f"{API}/reports/events")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        total_kpi = next((k for k in body["kpis"] if "total" in k["label"].lower()), None)
        assert total_kpi is not None, body["kpis"]
        assert str(total_kpi["value"]) in ("1", "1.0"), (
            f"{user.title}'s events report should show exactly 1 event, got {total_kpi}"
        )


# ---------------------------------------------------------------------------
# Generic export endpoint (CSV/XLSX/PDF) — the export-report use case's own
# Snapshot, a separate construction site from the per-module reports above.
# ---------------------------------------------------------------------------
def test_generic_export_never_leaks_across_users(harness):
    client, current, user_a, user_b = harness

    _as(current, user_b)
    resp_b = client.get(f"{API}/reports/export", params={"kind": "publications", "format": "csv"})
    assert resp_b.status_code == 200, resp_b.text
    assert "Alice" not in resp_b.text

    _as(current, user_a)
    resp_a = client.get(f"{API}/reports/export", params={"kind": "publications", "format": "csv"})
    assert resp_a.status_code == 200, resp_a.text
    assert "Alice" in resp_a.text


def test_generic_export_of_academic_cv_never_leaks_across_users(harness):
    """The specific bug found in this phase: the generic /reports/export
    endpoint dispatches to build_academic_cv() too, and that call site was
    passing no user_id at all — bypassing Academic CV's own, otherwise
    correct, scoping when reached through this path."""
    client, current, user_a, user_b = harness

    _as(current, user_b)
    resp_b = client.get(f"{API}/reports/export", params={"kind": "academic_cv", "format": "csv"})
    assert resp_b.status_code == 200, resp_b.text
    assert "Alice" not in resp_b.text, "generic export bypassed Academic CV's own user scoping"

    _as(current, user_a)
    resp_a = client.get(f"{API}/reports/export", params={"kind": "academic_cv", "format": "csv"})
    assert resp_a.status_code == 200, resp_a.text
    assert "Alice" in resp_a.text


# ---------------------------------------------------------------------------
# Academic CV's own dedicated endpoints (already correct before this phase;
# regression-guard so a future change can't quietly break them).
# ---------------------------------------------------------------------------
def test_academic_cv_dedicated_endpoint_still_scoped_correctly(harness):
    client, current, user_a, user_b = harness

    _as(current, user_b)
    resp_b = client.get(f"{API}/reports/academic-cv")
    assert resp_b.status_code == 200, resp_b.text
    assert "Alice" not in resp_b.text

    _as(current, user_a)
    resp_a = client.get(f"{API}/reports/academic-cv")
    assert resp_a.status_code == 200, resp_a.text
    assert "Alice" in resp_a.text


def test_academic_cv_dedicated_export_still_scoped_correctly(harness):
    client, current, user_a, user_b = harness

    _as(current, user_b)
    resp_b = client.get(f"{API}/reports/academic-cv/export", params={"format": "csv"})
    assert resp_b.status_code == 200, resp_b.text
    assert "Alice" not in resp_b.text

    _as(current, user_a)
    resp_a = client.get(f"{API}/reports/academic-cv/export", params={"format": "csv"})
    assert resp_a.status_code == 200, resp_a.text
    assert "Alice" in resp_a.text


# ---------------------------------------------------------------------------
# Every report route must require authentication at all (Depends(get_current_user)
# is declared once on the router, but prove it holds for each route we care about).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "path",
    [
        "dashboard", "export", "publications", "research", "faculty", "students",
        "teaching", "finance", "events", "committees", "analytics", "academic-cv",
        "academic-cv/export",
    ],
)
def test_every_report_route_requires_authentication(harness, path):
    client, current, user_a, user_b = harness
    app.dependency_overrides.pop(get_current_user, None)
    try:
        params = {"kind": "publications", "format": "csv"} if path == "export" else (
            {"format": "csv"} if path == "academic-cv/export" else {}
        )
        resp = client.get(f"{API}/reports/{path}", params=params)
        assert resp.status_code == 401, f"{path} did not require authentication: {resp.status_code}"
    finally:
        app.dependency_overrides[get_current_user] = lambda: current["user"]
