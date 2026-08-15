"""L1 ACL propagation service (ADR-009).

Every derived knowledge artifact carries the source object's ACL scope. This
service writes ``acl_scope`` onto the derived projection rows (search
documents, content, chunks, claims, CDM blocks) from a source document object's
scope, so retrieval/evidence can pre-filter without a second object lookup.

Semantics (per the frozen architecture and the second-pass audit): the scope is
the source object's OWN ACL scope (``object_acl_scope``). We preserve the
existing stricter-of semantics where relationships already derive it; we do NOT
invent role-union semantics (that is deferred to L9/L12).
"""

from __future__ import annotations

from sqlalchemy import text, update
from sqlalchemy.orm import Session

from app.application.use_cases.object_acl import object_acl_scope
from app.domain.entities.object import UniversalObject
from app.infrastructure.db.models.cdm_block_model import CdmBlockModel
from app.infrastructure.db.models.claim_model import ClaimModel
from app.infrastructure.db.models.document_chunk_model import DocumentChunkModel
from app.infrastructure.db.models.document_content_model import DocumentContentModel
from app.infrastructure.db.models.search_document_model import SearchDocumentModel


class AclScopePropagator:
    """(infrastructure layer — does SQL updates on derived projection tables.)"""
    """Stamp ``acl_scope`` on every derived row of one source object.

    Call inside the same transaction as the source object write that changed
    its ACL, or when a projection row is first created. Idempotent.

    Covers: search_documents, document_contents, document_chunks, claims,
    cdm_blocks, and the document_search_fts projection. The FTS row update is
    guarded so a missing FTS table (pre-0012 / no-FTS harness) never breaks
    the drain.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def propagate(self, source: UniversalObject) -> None:
        scope = object_acl_scope(source)
        doc_id = str(source.id)

        self._session.execute(
            update(SearchDocumentModel)
            .where(SearchDocumentModel.object_id == doc_id)
            .values(acl_scope=scope)
        )
        self._session.execute(
            update(DocumentContentModel)
            .where(DocumentContentModel.object_id == doc_id)
            .values(acl_scope=scope)
        )
        self._session.execute(
            update(DocumentChunkModel)
            .where(DocumentChunkModel.document_id == doc_id)
            .values(acl_scope=scope)
        )
        self._session.execute(
            update(ClaimModel)
            .where(ClaimModel.source_document_id == doc_id)
            .values(acl_scope=scope)
        )
        self._session.execute(
            update(CdmBlockModel)
            .where(CdmBlockModel.document_id == doc_id)
            .values(acl_scope=scope)
        )
        try:
            self._session.execute(
                text(
                    "UPDATE document_search_fts SET acl_scope = :scope "
                    "WHERE object_id = :oid"
                ),
                {"scope": scope, "oid": doc_id},
            )
        except Exception:  # noqa: BLE001 — missing FTS table degrades silently
            pass
