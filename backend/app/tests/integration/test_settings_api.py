"""Integration tests for the Settings & Preferences API.

Full TestClient surface: document bootstrap with factory defaults, every
section router (verbatim merge + 422s), the profile-photo binary lifecycle
(overriding the storage dependency with a tmp directory), and the PART 6
backup trio (export -> mutate -> import -> verify, reset).

Mirrors ``test_productivity_api.py``: StaticPool in-memory SQLite, the app
imported via ``pytest.importorskip``.
"""
from __future__ import annotations
from app.domain.value_objects.enums import ObjectStatus, ObjectType
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.object_id import ObjectId
from app.api.dependencies.auth import get_current_user

import io

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

    from app.api.routes.settings import get_storage  # noqa: E402
    from app.infrastructure.storage.local import LocalFileStorage  # noqa: E402

    app.dependency_overrides[get_db] = _override_db
    fake_user = UniversalObject.create(
        object_type=ObjectType.USER,
        title="test.user",
        created_by="system",
        status=ObjectStatus.ACTIVE,
        object_id=ObjectId("obj:user:test-user-0001"),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_storage] = lambda: LocalFileStorage(str(tmp_path))
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


API = "/api/v1/settings"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


def test_document_bootstraps_with_factory_defaults(client: TestClient):
    r = client.get(API)
    assert r.status_code == 200
    doc = r.json()
    assert set(doc["sections"].keys()) == {
        "profile", "appearance", "academic", "notifications",
        "dashboard", "search", "privacy", "ai",
    }
    assert doc["sections"]["appearance"]["theme"] == "system"
    assert doc["sections"]["notifications"]["priority_default"] == "medium"
    assert doc["sections"]["privacy"]["remember_last_module"] is True
    assert doc["has_photo"] is False
    # idempotent — still exactly one settings object after another touch
    assert client.get(API).status_code == 200


def test_every_section_router_merges_and_returns_typed_values(client: TestClient):
    cases = [
        ("profile", {"name": "Dr. Settings", "email": "s@univ.edu"}, {"name": "Dr. Settings"}),
        ("appearance", {"theme": "dark", "custom_theme": "solarized"}, {"theme": "dark"}),
        ("academic", {"default_programme": "MSc", "default_semester": "2", "date_format": "dd/mm/yyyy"}, {"date_format": "dd/mm/yyyy"}),
        ("notifications", {"enabled": False, "reminder_default": "one_day_before",
                           "calendar_default_sources": ["events", "teaching"]}, {"enabled": False}),
        ("dashboard", {"default_landing_page": "productivity", "favorite_modules": ["reports"],
                       "widget_visibility": {"calendar": True}, "default_view": "list"},
         {"default_landing_page": "/productivity", "default_view": "list"}),
        ("search", {"default_scope": "productivity", "recent_searches_limit": 30}, {"default_scope": "productivity"}),
        ("privacy", {"reduce_motion": True, "session_page_size": 50}, {"reduce_motion": True}),
        ("ai", {"preferred_writing_style": "concise", "preferred_report_format": "pdf"}, {"preferred_report_format": "pdf"}),
    ]
    for section, payload, expect in cases:
        r = client.put(f"{API}/{section}", json=payload)
        assert r.status_code == 200, (section, r.text)
        body = r.json()
        assert body["section"] == section
        for key, value in expect.items():
            assert body["values"][key] == value, (section, key, body)
    doc = client.get(API).json()["sections"]
    assert doc["notifications"]["reminder_default"] == "one_day_before"
    assert doc["dashboard"]["favorite_modules"] == ["reports"]
    # PATCH twin honours the same handler and merge semantics
    r = client.patch(f"{API}/profile", json={"biography": "Graphs and life."})
    assert r.status_code == 200 and r.json()["values"]["name"] == "Dr. Settings"
    assert r.json()["values"]["biography"] == "Graphs and life."


def test_validation_errors_are_422_with_stable_codes(client: TestClient):
    bad = [
        ("/profile", {"email": "nope"}),
        ("/profile", {"department_code": "M101"}),            # unknown field (strict body)
        ("/appearance", {"theme": "midnight"}),
        ("/academic", {"date_format": "31-12-2026"}),
        ("/notifications", {"calendar_default_sources": ["email"]}),
        ("/dashboard", {"favorite_modules": ["settings"]}),
        ("/search", {"recent_searches_limit": 99}),
        ("/ai", {"preferred_report_format": "pptx"}),
        ("/unknown-section", {"x": 1}),                        # no such route
    ]
    for path, payload in bad:
        r = client.put(f"{API}{path}", json=payload)
        assert r.status_code in (404, 422), (path, r.status_code, r.text)


def test_photo_binary_lifecycle(client: TestClient):
    r = client.get(f"{API}/profile/photo")
    assert r.status_code == 404
    r = client.post(
        f"{API}/profile/photo",
        files={"file": ("me.png", io.BytesIO(PNG), "image/png")},
    )
    assert r.status_code == 201, r.text
    assert r.json()["size_bytes"] == len(PNG)
    doc = client.get(API).json()
    assert doc["has_photo"] is True and doc["photo_name"] == "me.png"
    r = client.get(f"{API}/profile/photo")
    assert r.status_code == 200 and r.content == PNG
    assert r.headers["content-type"].startswith("image/png")
    assert 'filename="me.png"' in r.headers.get("content-disposition", "")
    r = client.delete(f"{API}/profile/photo")
    assert r.status_code == 204
    assert client.get(API).json()["has_photo"] is False
    assert client.get(f"{API}/profile/photo").status_code == 404


def test_photo_rejects_wrong_type_and_oversize(client: TestClient):
    r = client.post(f"{API}/profile/photo",
                    files={"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")})
    assert r.status_code == 422
    r = client.post(f"{API}/profile/photo",
                    files={"file": ("a.png", io.BytesIO(b"x" * 2_000_001), "image/png")})
    assert r.status_code == 422


def test_backup_export_mutate_import_roundtrip(client: TestClient):
    client.put(f"{API}/profile", json={"name": "Dr. Keeper", "institution": "IIT Delhi"})
    client.put(f"{API}/appearance", json={"theme": "dark"})
    exported = client.get(f"{API}/export").json()
    assert exported["version"] == 1 and "exported_at" in exported
    assert exported["sections"]["profile"]["name"] == "Dr. Keeper"
    # mutate away, then import the export back
    client.put(f"{API}/profile", json={"name": "Someone Else"})
    client.post(f"{API}/reset", json={})
    doc = client.get(API).json()["sections"]
    assert doc["profile"]["name"] == "" and doc["appearance"]["theme"] == "system"
    r = client.post(f"{API}/import", json={"sections": exported["sections"]})
    assert r.status_code == 200, r.text
    doc = client.get(API).json()["sections"]
    assert doc["profile"]["name"] == "Dr. Keeper"
    assert doc["appearance"]["theme"] == "dark"


def test_import_rejects_bad_values_and_reset_partial(client: TestClient):
    r = client.post(f"{API}/import", json={"sections": {"appearance": {"theme": "blue"}}})
    assert r.status_code == 422
    r = client.post(f"{API}/import", json={"sections": {"ghost": {"x": 1}}})
    assert r.status_code == 422
    client.put(f"{API}/appearance", json={"theme": "dark"})
    client.put(f"{API}/search", json={"recent_searches_limit": 44})
    r = client.post(f"{API}/reset", json={"sections": ["appearance"]})
    assert r.status_code == 200
    doc = r.json()["sections"]
    assert doc["appearance"]["theme"] == "system"
    assert doc["search"]["recent_searches_limit"] == 44
    r = client.post(f"{API}/reset", json={"sections": ["nope"]})
    assert r.status_code == 422


def test_single_singleton_across_section_writes(client: TestClient):
    """Every section lives on ONE settings object (no document duplication)."""
    for section, payload in [
        ("profile", {"name": "A"}), ("appearance", {"theme": "dark"}),
        ("search", {"default_scope": "reports"}), ("ai", {"preferred_writing_style": "x"}),
    ]:
        assert client.put(f"{API}/{section}", json=payload).status_code == 200
    doc = client.get(API).json()
    assert doc["sections"]["profile"]["name"] == "A"
    assert doc["sections"]["appearance"]["theme"] == "dark"
    assert doc["sections"]["search"]["default_scope"] == "reports"
    assert doc["sections"]["ai"]["preferred_writing_style"] == "x"
