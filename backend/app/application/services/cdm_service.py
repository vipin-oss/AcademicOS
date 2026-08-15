"""L1 CDM block service (Blueprint §11).

Writes/reads structured-document blocks in reading order. Engines (L2) call
``replace_blocks`` to write a document version's block set; ``by_document``
serves the CDM read surface. Blocks are format-agnostic (block types include
equation, table, image region, diagram — stored now; the parsers are L2).
"""

from __future__ import annotations

import datetime as dt
import uuid

from app.application.ports.cdm_store import CdmStore
from app.domain.value_objects.cdm import CdmBlock, CdmBlockType


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


class CdmService:
    def __init__(self, store: CdmStore) -> None:
        self._store = store

    def replace_blocks(
        self,
        *,
        document_id: str,
        version: int,
        blocks: list[CdmBlock],
        acl_scope: str | None = None,
    ) -> int:
        """Persist a document version's block set (replace-for-document).

        Idempotent for identical input. Returns the number of blocks written.
        """
        stamped = [
            CdmBlock(
                block_id=b.block_id or f"block:{uuid.uuid4().hex[:16]}",
                document_id=document_id,
                version=version,
                block_type=b.block_type,
                order=b.order,
                payload=b.payload,
                parent_block_id=b.parent_block_id,
                acl_scope=b.acl_scope if b.acl_scope is not None else acl_scope,
                page=b.page,
                extraction_confidence=b.extraction_confidence,
            )
            for b in blocks
        ]
        self._store.replace_for_document(document_id, version, stamped)
        return len(stamped)

    def by_document(self, document_id: str, version: int | None = None) -> list[CdmBlock]:
        return self._store.by_document(document_id, version)

    def delete_by_document(self, document_id: str) -> None:
        self._store.delete_by_document(document_id)

    @staticmethod
    def make_block(
        block_type: CdmBlockType,
        order: int,
        *,
        payload: dict | None = None,
        parent_block_id: str | None = None,
        page: int | None = None,
        extraction_confidence: float | None = None,
        block_id: str | None = None,
    ) -> CdmBlock:
        """Factory for tests and L2 engines to build a block before writing."""
        return CdmBlock(
            block_id=block_id or f"block:{uuid.uuid4().hex[:16]}",
            document_id="",
            version=0,
            block_type=block_type,
            order=order,
            payload=payload or {},
            parent_block_id=parent_block_id,
            page=page,
            extraction_confidence=extraction_confidence,
        )
