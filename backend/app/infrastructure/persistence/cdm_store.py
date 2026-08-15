"""SQL implementation of the CDM block store (L1, Blueprint §11).

Mirrors the other store conventions: dialect-agnostic writes, caller owns the
transaction. ``block_id`` is the idempotency key; a document version's block
set is replaced (delete-then-insert) so stale blocks never coexist.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.application.ports.cdm_store import CdmStore
from app.domain.value_objects.cdm import CdmBlock, CdmBlockType
from app.infrastructure.db.models.cdm_block_model import CdmBlockModel


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def _to_model(block: CdmBlock, now: str) -> CdmBlockModel:
    return CdmBlockModel(
        block_id=block.block_id,
        document_id=block.document_id,
        version=block.version,
        block_type=block.block_type.value,
        order=block.order,
        payload=block.payload,
        parent_block_id=block.parent_block_id,
        acl_scope=block.acl_scope,
        page=block.page,
        extraction_confidence=block.extraction_confidence,
        created_at=now,
    )


def _from_model(row: CdmBlockModel) -> CdmBlock:
    return CdmBlock(
        block_id=row.block_id,
        document_id=row.document_id,
        version=row.version,
        block_type=CdmBlockType(row.block_type),
        order=row.order,
        payload=row.payload,
        parent_block_id=row.parent_block_id,
        acl_scope=row.acl_scope,
        page=row.page,
        extraction_confidence=row.extraction_confidence,
    )


class SQLCdmStore(CdmStore):
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_for_document(
        self, document_id: str, version: int, blocks: list[CdmBlock]
    ) -> None:
        self._session.execute(
            delete(CdmBlockModel).where(CdmBlockModel.document_id == document_id)
        )
        now = _utcnow_iso()
        for block in blocks:
            self._session.add(_to_model(block, now))

    def by_document(
        self, document_id: str, version: int | None = None
    ) -> list[CdmBlock]:
        stmt = select(CdmBlockModel).where(CdmBlockModel.document_id == document_id)
        if version is not None:
            stmt = stmt.where(CdmBlockModel.version == version)
        rows = self._session.execute(stmt.order_by(CdmBlockModel.order)).scalars().all()
        return [_from_model(r) for r in rows]

    def delete_by_document(self, document_id: str) -> None:
        self._session.execute(
            delete(CdmBlockModel).where(CdmBlockModel.document_id == document_id)
        )

    def count(self, document_id: str) -> int:
        return int(
            self._session.execute(
                select(func.count())
                .select_from(CdmBlockModel)
                .where(CdmBlockModel.document_id == document_id)
            ).scalar_one()
        )
