"""L1 CDM block store tests (Blueprint §11, ADR-024)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.services.cdm_service import CdmService
from app.domain.value_objects.cdm import CdmBlock, CdmBlockType
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.models.cdm_block_model import CdmBlockModel  # noqa: F401
from app.infrastructure.persistence.cdm_store import SQLCdmStore


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


def _block(t, order, **kw):
    return CdmService.make_block(block_type=t, order=order, **kw)


def test_write_and_read_reading_order(db):
    service = CdmService(SQLCdmStore(db))
    blocks = [
        _block(CdmBlockType.HEADING, 0, payload={"text": "Title"}),
        _block(CdmBlockType.PARAGRAPH, 1, payload={"text": "Body"}),
        _block(CdmBlockType.EQUATION, 2, payload={"formula": "E=mc^2"}),
        _block(CdmBlockType.TABLE, 3, payload={"cells": [["a", "b"]]}),
    ]
    n = service.replace_blocks(
        document_id="obj:document:1", version=1, blocks=blocks,
        acl_scope='{"owner":"u:1"}',
    )
    assert n == 4
    out = service.by_document("obj:document:1")
    assert [b.block_type for b in out] == [
        CdmBlockType.HEADING, CdmBlockType.PARAGRAPH,
        CdmBlockType.EQUATION, CdmBlockType.TABLE,
    ]
    assert all(b.acl_scope == '{"owner":"u:1"}' for b in out)


def test_equation_block_is_storable_not_parsed(db):
    service = CdmService(SQLCdmStore(db))
    service.replace_blocks(
        document_id="obj:document:1", version=1,
        blocks=[_block(CdmBlockType.EQUATION, 0, payload={"formula": "x^2"})],
    )
    out = service.by_document("obj:document:1")
    assert out[0].block_type is CdmBlockType.EQUATION
    assert out[0].payload["formula"] == "x^2"


def test_replace_is_idempotent(db):
    service = CdmService(SQLCdmStore(db))
    blocks = [_block(CdmBlockType.PARAGRAPH, 0, payload={"text": "A"})]
    service.replace_blocks(document_id="obj:document:1", version=1, blocks=blocks)
    service.replace_blocks(document_id="obj:document:1", version=1, blocks=blocks)
    assert len(service.by_document("obj:document:1")) == 1


def test_delete_by_document(db):
    service = CdmService(SQLCdmStore(db))
    service.replace_blocks(
        document_id="obj:document:1", version=1,
        blocks=[_block(CdmBlockType.PARAGRAPH, 0)],
    )
    service.delete_by_document("obj:document:1")
    assert len(service.by_document("obj:document:1")) == 0
