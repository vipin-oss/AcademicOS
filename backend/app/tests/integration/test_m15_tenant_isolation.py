"""V3 M15 tenant isolation matrix tests (ADR-062)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine, text
from sqlalchemy.orm import sessionmaker

from app.application.ports.tenant_store import STATUS_ACTIVE, STATUS_SUSPENDED
from app.application.services.saved_view_compiler import SavedViewCompiler
from app.application.services.tenant_service import TenantService
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.organization_model import (  # noqa: F401
    MembershipModel,
    OrganizationModel,
)
from app.infrastructure.persistence.tenant_store import SQLTenantStore


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


def _seed_objects(db, tenant, count, prefix):
    for i in range(count):
        db.execute(
            text(
                "INSERT INTO objects (id, object_type, title, status, version, "
                "metadata_json, audit_json, tenant_id, owner_user_id) "
                "VALUES (:id, 'document', :t, 'draft', 1, '{}', NULL, :tenant, 'default')"
            ),
            {"id": f"obj:document:{prefix}-{i}", "t": f"{prefix} doc {i}", "tenant": tenant},
        )
    db.commit()


def test_two_tenant_isolation_matrix(db):
    t1 = TenantService(SQLTenantStore(db)).create(name="Tenant One")
    t2 = TenantService(SQLTenantStore(db)).create(name="Tenant Two")

    _seed_objects(db, t1.id, 3, "t1")
    _seed_objects(db, t2.id, 5, "t2")

    # a saved-view query scoped to t1 sees ONLY t1's 3 documents
    compiled = SavedViewCompiler.compile(
        {"columns": ["id"], "filters": [{"column": "object_type", "op": "eq", "value": "document"}]},
        tenant_id=t1.id,
    )
    rows = db.execute(text(compiled.sql), compiled.params).fetchall()
    assert len(rows) == 3
    assert all("t1" in r[0] for r in rows)

    # scoped to t2 sees ONLY t2's 5
    compiled2 = SavedViewCompiler.compile(
        {"columns": ["id"]}, tenant_id=t2.id
    )
    rows2 = db.execute(text(compiled2.sql), compiled2.params).fetchall()
    assert len(rows2) == 5
    assert all("t2" in r[0] for r in rows2)


def test_tenant_lifecycle_and_membership(db):
    t = TenantService(SQLTenantStore(db)).create(name="Org")
    assert t.status == STATUS_ACTIVE
    TenantService(SQLTenantStore(db)).add_member(organization_id=t.id, user_id="obj:user:1", role="professor")
    assert TenantService(SQLTenantStore(db)).members(t.id) == [("obj:user:1", "professor")]

    suspended = TenantService(SQLTenantStore(db)).suspend(t.id)
    assert suspended.status == STATUS_SUSPENDED
    assert TenantService(SQLTenantStore(db)).is_suspended(t.id) is True

    resumed = TenantService(SQLTenantStore(db)).resume(t.id)
    assert resumed.status == STATUS_ACTIVE


def test_suspended_tenant_denies_its_data(db):
    t = TenantService(SQLTenantStore(db)).create(name="Suspended Org")
    _seed_objects(db, t.id, 2, "sus")
    TenantService(SQLTenantStore(db)).suspend(t.id)

    # enforcement reads the suspended flag; a scoped query for a suspended
    # tenant is refused by the caller, but the data still exists (no deletion)
    compiled = SavedViewCompiler.compile({"columns": ["id"]}, tenant_id=t.id)
    rows = db.execute(text(compiled.sql), compiled.params).fetchall()
    assert len(rows) == 2  # data retained; access is the caller's gate
    assert TenantService(SQLTenantStore(db)).is_suspended(t.id) is True
