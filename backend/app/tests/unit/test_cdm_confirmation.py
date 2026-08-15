"""L3 CDM-block confirmation tests (ADR-032)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.cdm_confirmation import CdmConfirmationService
from app.infrastructure.db.models.cdm_decision_model import CdmDecisionModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.persistence.cdm_decision_store import SQLCdmDecisionStore


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_approve_block_records_decision(db):
    svc = CdmConfirmationService(SQLCdmDecisionStore(db))
    record = svc.approve("block:1", reviewer="u:1", notes="ok", acl_scope='{"owner":"u:1"}')
    assert record.resulting_status == "confirmed"
    assert len(SQLCdmDecisionStore(db).by_block("block:1")) == 1


def test_reject_block_records_decision(db):
    svc = CdmConfirmationService(SQLCdmDecisionStore(db))
    record = svc.reject("block:1", reviewer="u:1")
    assert record.resulting_status == "rejected"
    assert len(SQLCdmDecisionStore(db).by_block("block:1")) == 1
