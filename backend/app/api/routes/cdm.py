"""CDM API (L1, Blueprint §11 + ADR-022 — OpenAPI contract surface).

Surfaces the structured-document block store:
  - GET /cdm/documents/{document_id}      blocks of a document (reading order)
  - POST /cdm/documents/{document_id}     write a document version's block set

Engines (L2) write CDM blocks here through the L1 contract; the format is
agnostic (heading/section/table/figure/caption/footnote/equation/image_region/
diagram/slide/...). Reading order is carried as data (``order``).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.application.services.cdm_service import CdmService
from app.domain.value_objects.cdm import CdmBlock, CdmBlockType
from app.infrastructure.db.session import get_db
from app.infrastructure.persistence.cdm_store import SQLCdmStore

router = APIRouter(
    prefix="/cdm",
    tags=["cdm"],
    dependencies=[Depends(get_current_user)],
)


def _store(db: Session) -> CdmService:
    return CdmService(SQLCdmStore(db))


class BlockIn(BaseModel):
    block_type: str
    order: int
    payload: dict[str, Any] = Field(default_factory=dict)
    parent_block_id: str | None = None
    page: int | None = None
    extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    block_id: str | None = None


class CdmWriteIn(BaseModel):
    version: int = 1
    acl_scope: str | None = None
    blocks: list[BlockIn]


class BlockOut(BaseModel):
    block_id: str
    block_type: str
    order: int
    payload: dict[str, Any]
    parent_block_id: str | None
    page: int | None
    extraction_confidence: float | None


class CdmWriteOut(BaseModel):
    document_id: str
    version: int
    written: int


@router.get("/documents/{document_id}", response_model=list[BlockOut])
def get_cdm(
    document_id: str,
    version: int | None = None,
    db: Session = Depends(get_db),
) -> list[BlockOut]:
    blocks = _store(db).by_document(document_id, version)
    return [
        BlockOut(
            block_id=b.block_id,
            block_type=b.block_type.value,
            order=b.order,
            payload=b.payload,
            parent_block_id=b.parent_block_id,
            page=b.page,
            extraction_confidence=b.extraction_confidence,
        )
        for b in blocks
    ]


@router.post(
    "/documents/{document_id}",
    response_model=CdmWriteOut,
    status_code=status.HTTP_201_CREATED,
)
def write_cdm(
    document_id: str,
    body: CdmWriteIn,
    db: Session = Depends(get_db),
) -> CdmWriteOut:
    blocks = [
        CdmBlock(
            block_id=b.block_id or f"block-{document_id}-{b.order}",
            document_id=document_id,
            version=body.version,
            block_type=CdmBlockType(b.block_type),
            order=b.order,
            payload=b.payload,
            parent_block_id=b.parent_block_id,
            page=b.page,
            extraction_confidence=b.extraction_confidence,
        )
        for b in body.blocks
    ]
    written = _store(db).replace_blocks(
        document_id=document_id,
        version=body.version,
        blocks=blocks,
        acl_scope=body.acl_scope,
    )
    return CdmWriteOut(document_id=document_id, version=body.version, written=written)
