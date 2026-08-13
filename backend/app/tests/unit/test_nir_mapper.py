"""L2 NIR mapper tests (ADR-028)."""

from __future__ import annotations

import pytest
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.application.dtos.nir import NirDocument, NirElement, NirElementType, NirImage
from app.application.services.cdm_service import CdmService
from app.application.services.nir_mapper import NirMapper
from app.domain.value_objects.cdm import CdmBlockType
from app.infrastructure.db.models.cdm_block_model import CdmBlockModel  # noqa: F401
from app.infrastructure.db.models.object_model import Base
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


def _nir(**kw) -> NirDocument:
    base = {
        "source_id": "obj:document:1",
        "media_kind": "text_layout",
        "version": 1,
        "engine": "test",
        "engine_version": 1,
        "elements": (),
        "images": (),
    }
    base.update(kw)
    return NirDocument(**base)


def test_maps_structured_elements_to_cdm_blocks(db):
    mapper = NirMapper(CdmService(SQLCdmStore(db)))
    nir = _nir(
        elements=(
            NirElement(NirElementType.HEADING, 0, text="Title"),
            NirElement(NirElementType.TABLE, 1, value={"rows": [["a", "b"]]}),
            NirElement(NirElementType.EQUATION, 2, text="E=mc^2"),
        )
    )
    blocks = mapper.to_cdm_blocks(nir, document_id="obj:document:1")
    types = [b.block_type for b in blocks]
    assert types == [CdmBlockType.HEADING, CdmBlockType.TABLE, CdmBlockType.EQUATION]
    assert blocks[0].order == 0 and blocks[1].order == 1 and blocks[2].order == 2


def test_maps_images_to_image_region_blocks(db):
    mapper = NirMapper(CdmService(SQLCdmStore(db)))
    nir = _nir(
        images=(NirImage(image_id="img-1", page=1, bbox=(0, 0, 10, 10), caption="A fig"),)
    )
    blocks = mapper.to_cdm_blocks(nir, document_id="obj:document:1")
    assert blocks[-1].block_type is CdmBlockType.IMAGE_REGION
    assert blocks[-1].payload["caption"] == "A fig"


def test_write_cdm_persists_and_counts(db):
    mapper = NirMapper(CdmService(SQLCdmStore(db)))
    nir = _nir(
        elements=(NirElement(NirElementType.PARAGRAPH, 0, text="hi"),)
    )
    count = mapper.write_cdm(nir, document_id="obj:document:1", acl_scope='{"owner":"u:1"}')
    assert count == 1
    stored = CdmService(SQLCdmStore(db)).by_document("obj:document:1")
    assert len(stored) == 1
    assert stored[0].acl_scope == '{"owner":"u:1"}'


def test_element_spans_derived(db):
    mapper = NirMapper(CdmService(SQLCdmStore(db)))
    nir = _nir(
        elements=(NirElement(NirElementType.TEXT, 0, page=2, bbox=(0, 0, 1, 1)),)
    )
    spans = mapper.element_spans(nir)
    assert len(spans) == 1
    assert spans[0].page == 2
