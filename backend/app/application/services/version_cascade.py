"""L1 file-version -> claim/CDM supersession cascade (ADR-021).

When a document is replaced by a NEWER file version:

1. old CDM blocks of the previous version are SUPERSEDED (marked, not deleted);
2. old PROPOSED/CONFIRMED claims of the previous version are SUPERSEDED by new
   PROPOSED placeholders on the new version (re-extraction, an L2 engine,
   proposes the actual values);
3. nothing is silently merged or deleted; historical/as-of queries keep the
   supersede chain.

Duplicate re-uploads of identical normalized content are NOT a version
replacement (they remain content-identity links per ADR-002b) — that decision
lives with the identity registry, not here.
"""

from __future__ import annotations

import dataclasses

from app.application.ports.cdm_store import CdmStore
from app.application.services.claim_service import ClaimService
from app.domain.value_objects.cdm import CdmBlock


@dataclasses.dataclass
class VersionCascadeResult:
    document_id: str
    old_version: int
    new_version: int
    cdm_blocks_superseded: int = 0
    claims_superseded: int = 0


class VersionCascade:
    """Coordinates CDM + claim supersession on a version replacement."""

    def __init__(
        self,
        claim_service: ClaimService,
        cdm_store: CdmStore,
        *,
        mark_old_cdm_superseded: bool = True,
    ) -> None:
        self._claims = claim_service
        self._cdm = cdm_store
        self._mark_old_cdm = mark_old_cdm_superseded

    def run(
        self,
        *,
        document_id: str,
        old_version: int,
        new_version: int,
    ) -> VersionCascadeResult:
        claims_superseded = self._claims.supersede_for_source_version(
            document_id, old_version, new_version
        )

        cdm_blocks_superseded = 0
        if self._mark_old_cdm:
            old_blocks = self._cdm.by_document(document_id, old_version)
            # Mark each old block as superseded in place (append-only
            # lifecycle: the block payload is preserved; a new version will
            # replace the block set via CdmService.replace_blocks).
            marked: list[CdmBlock] = []
            for b in old_blocks:
                payload = dict(b.payload)
                payload["superseded"] = True
                payload["superseded_by_version"] = new_version
                marked.append(
                    CdmBlock(
                        block_id=b.block_id,
                        document_id=b.document_id,
                        version=b.version,
                        block_type=b.block_type,
                        order=b.order,
                        payload=payload,
                        parent_block_id=b.parent_block_id,
                        acl_scope=b.acl_scope,
                        page=b.page,
                        extraction_confidence=b.extraction_confidence,
                    )
                )
            if marked:
                self._cdm.replace_for_document(document_id, old_version, marked)
                cdm_blocks_superseded = len(marked)

        return VersionCascadeResult(
            document_id=document_id,
            old_version=old_version,
            new_version=new_version,
            cdm_blocks_superseded=cdm_blocks_superseded,
            claims_superseded=claims_superseded,
        )
