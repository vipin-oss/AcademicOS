"""L2 NIR mapper (ADR-028).

Converts a transient ``NirDocument`` into the existing L1 contracts:
``CdmBlock`` (+ ``Span``) via ``CdmService``, and optionally proposed ``Claim``
candidates via ``ClaimService``. This is the format-agnostic bridge between
engine output and the L1 knowledge plane — no engine library is imported here.
"""

from __future__ import annotations

import uuid

from app.application.dtos.nir import NirDocument, NirElementType
from app.application.services.cdm_service import CdmService
from app.domain.value_objects.cdm import CdmBlock, CdmBlockType
from app.domain.value_objects.span import Span

#: NIR element type -> CDM block type (best-effort, format-agnostic).
_NIR_TO_CDM: dict[NirElementType, CdmBlockType] = {
    NirElementType.TEXT: CdmBlockType.PARAGRAPH,
    NirElementType.HEADING: CdmBlockType.HEADING,
    NirElementType.PARAGRAPH: CdmBlockType.PARAGRAPH,
    NirElementType.LIST: CdmBlockType.LIST,
    NirElementType.TABLE: CdmBlockType.TABLE,
    NirElementType.TABLE_ROW: CdmBlockType.TABLE,
    NirElementType.TABLE_CELL: CdmBlockType.TABLE_CELL,
    NirElementType.FIGURE: CdmBlockType.FIGURE,
    NirElementType.CAPTION: CdmBlockType.CAPTION,
    NirElementType.FOOTNOTE: CdmBlockType.FOOTNOTE,
    NirElementType.HEADER: CdmBlockType.HEADER,
    NirElementType.FOOTER: CdmBlockType.FOOTER,
    NirElementType.EQUATION: CdmBlockType.EQUATION,
    NirElementType.IMAGE: CdmBlockType.IMAGE_REGION,
    NirElementType.IMAGE_REGION: CdmBlockType.IMAGE_REGION,
    NirElementType.DIAGRAM: CdmBlockType.DIAGRAM,
    NirElementType.SLIDE: CdmBlockType.SLIDE,
    NirElementType.SHEET: CdmBlockType.TABLE,
    NirElementType.SHEET_CELL: CdmBlockType.TABLE_CELL,
    NirElementType.METADATA: CdmBlockType.METADATA,
    NirElementType.OTHER: CdmBlockType.OTHER,
}


class NirMapper:
    """Maps NIR to L1 CDM blocks (and optionally proposed claims)."""

    def __init__(self, cdm_service: CdmService) -> None:
        self._cdm = cdm_service

    def to_cdm_blocks(
        self,
        nir: NirDocument,
        *,
        document_id: str,
        acl_scope: str | None = None,
    ) -> list[CdmBlock]:
        """Convert every NIR element (+ image) to a CDM block in order."""
        blocks: list[CdmBlock] = []
        order = 0
        for element in nir.elements:
            block_type = _NIR_TO_CDM.get(element.element_type, CdmBlockType.OTHER)
            payload = dict(element.value)
            if element.text:
                payload["text"] = element.text
            if element.parent_id:
                payload["parent_id"] = element.parent_id
            blocks.append(
                CdmBlock(
                    block_id=element.element_id or f"block:{uuid.uuid4().hex[:16]}",
                    document_id=document_id,
                    version=nir.version,
                    block_type=block_type,
                    order=order,
                    payload=payload,
                    acl_scope=acl_scope,
                    page=element.page,
                    extraction_confidence=element.extraction_confidence,
                )
            )
            order += 1
        for image in nir.images:
            payload = {"image_id": image.image_id}
            if image.caption:
                payload["caption"] = image.caption
            if image.blob_key:
                payload["blob_key"] = image.blob_key
            if image.width:
                payload["width"] = image.width
            if image.height:
                payload["height"] = image.height
            blocks.append(
                CdmBlock(
                    block_id=f"image:{image.image_id}",
                    document_id=document_id,
                    version=nir.version,
                    block_type=CdmBlockType.IMAGE_REGION,
                    order=order,
                    payload=payload,
                    acl_scope=acl_scope,
                    page=image.page,
                    extraction_confidence=image.extraction_confidence,
                )
            )
            order += 1
        return blocks

    @staticmethod
    def element_spans(nir: NirDocument) -> list[Span]:
        """All polymorphic spans derived from NIR elements/images."""
        spans: list[Span] = []
        for element in nir.elements:
            span = element.to_span(nir.source_id)
            if span is not None:
                spans.append(span)
        for image in nir.images:
            spans.append(image.span(nir.source_id))
        return spans

    def write_cdm(
        self,
        nir: NirDocument,
        *,
        document_id: str,
        acl_scope: str | None = None,
    ) -> int:
        """Persist the NIR as CDM blocks via CdmService; returns block count."""
        blocks = self.to_cdm_blocks(nir, document_id=document_id, acl_scope=acl_scope)
        self._cdm.replace_blocks(
            document_id=document_id,
            version=nir.version,
            blocks=blocks,
            acl_scope=acl_scope,
        )
        return len(blocks)
