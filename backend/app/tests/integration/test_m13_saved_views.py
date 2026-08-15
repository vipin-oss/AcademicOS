"""V3 M13 saved-view integration tests (ADR-060)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine, text
from sqlalchemy.orm import sessionmaker

from app.application.ports.saved_view_store import SavedViewRecord
from app.application.services.saved_view_compiler import SavedViewCompiler
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.saved_view_model import SavedViewModel  # noqa: F401
from app.infrastructure.persistence.saved_view_store import SQLSavedViewStore


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed(db):
    rows = [
        ("obj:document:1", "document", "Report A", "draft", 1),
        ("obj:document:2", "document", "Report B", "draft", 1),
        ("obj:user:1", "user", "alice", "active", 1),
    ]
    for oid, otype, title, status, ver in rows:
        db.execute(
            text(
                "INSERT INTO objects (id, object_type, title, status, version, "
                "metadata_json, audit_json, tenant_id, owner_user_id) "
                "VALUES (:id, :t, :title, :s, :v, '{}', NULL, 'default', 'default')"
            ),
            {"id": oid, "t": otype, "title": title, "s": status, "v": ver},
        )
    db.commit()


def test_compiled_query_runs_and_filters_by_tenant(db):
    _seed(db)
    compiled = SavedViewCompiler.compile(
        {"columns": ["id", "title"], "filters": [{"column": "object_type", "op": "eq", "value": "document"}]},
        tenant_id="default",
    )
    rows = db.execute(text(compiled.sql), compiled.params).fetchall()
    assert len(rows) == 2  # two documents, one user excluded


def test_aggregate_count_is_tenant_scoped(db):
    _seed(db)
    compiled = SavedViewCompiler.compile({"aggregate": "count"}, tenant_id="default")
    row = db.execute(text(compiled.sql), compiled.params).fetchone()
    assert row[0] == 3


def test_store_roundtrip_and_delete(db):
    store = SQLSavedViewStore(db)
    store.add(SavedViewRecord(id="v1", name="My docs", definition={"columns": ["title"]},
                              owner_user_id="obj:user:1", created_at="2026-01-01T00:00:00Z"))
    db.commit()
    assert store.get("v1").name == "My docs"
    assert len(store.list_for_owner("obj:user:1")) == 1
    store.delete("v1")
    db.commit()
    assert store.get("v1") is None
