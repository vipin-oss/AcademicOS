"""Use case: related documents via semantic similarity (Sprint M13.3).

Given a source document, return other documents ranked by semantic
similarity — "more like this" over the existing embedding/vector index.

Reuse-only (no new embedding abstraction, vector DB client, search pipeline,
ranking algorithm, or transport owner):

- **Embedder**: the EXISTING ``Embedder`` port, resolved by the route through
  the SAME dependency (``get_embedder``) the semantic-search route uses — so
  related documents uses the identical embedder identity and the vector
  collection dimensions already established by M12.
- **Vector repository**: the EXISTING ``VectorRepository.search`` nearest-
  neighbour behaviour (cosine similarity, deterministic ``object_id`` ties).
- **Source text**: the existing ``DocumentAnnotationService.extracted_text``
  intake pipeline (same source summarization/enrichment use).
- **Permission filtering**: the established R4 gate — every candidate is
  re-authorized against the authoritative object via ``PermissionEvaluator``
  (READ); the index is derived data, the object is the authority.

Safety contract:
- **Source permission**: READ on the source enforced before any text is
  loaded or embedded — unauthorized source content never reaches the embedder.
- **Result permission**: only documents the caller can READ are returned; a
  document is never returned merely because it is semantically similar.
- **Self-exclusion**: the source document never appears in its own results.
- **Honest degradation**: no/failed embedding or vector backend → empty
  results (never a crash, never fabricated similarity).
- **Deterministic**: order and scores are stable for the same index state.
- **Bounded**: ``limit`` is clamped to ``[1, _MAX_LIMIT]``.
- **No LLM provenance**: this is an embedding/search capability; the response
  carries only the related-document result contract (no fabricated
  provider/model/prompt fields).
"""
from __future__ import annotations

from app.application.dtos.ai import (
    RelatedDocumentItem,
    RelatedDocumentsResult,
)
from app.application.exceptions import (
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.application.ports.embedder import Embedder
from app.application.ports.file_storage import FileStorage
from app.application.ports.permission import PermissionEvaluator
from app.application.services.document_annotation_service import (
    DocumentAnnotationService,
)
from app.application.use_cases.auth.helpers import get_roles
from app.application.use_cases.object_acl import object_acl_scope

# Reuse the EXISTING search scoring convention (reciprocal-rank fusion) — not a
# new ranking algorithm. The ordering itself comes from vector_repository.search.
from app.application.use_cases.search.search_objects import _RRF_K, _SCORE_DECIMALS
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.repositories.vector_repository import VectorRepository
from app.domain.value_objects.enums import ObjectType, PermissionAction
from app.domain.value_objects.object_id import ObjectId

_DEFAULT_LIMIT = 10
_MAX_LIMIT = 50


class RelatedDocumentsUseCase:
    """Return documents semantically related to a source document."""

    def __init__(
        self,
        repository: ObjectRepository,
        annotation_service: DocumentAnnotationService,
        permission_evaluator: PermissionEvaluator,
        vector_repository: VectorRepository | None,
        embedder: Embedder | None,
    ) -> None:
        self._repository = repository
        self._annotation_service = annotation_service
        self._permission_evaluator = permission_evaluator
        self._vector_repository = vector_repository
        self._embedder = embedder

    def execute(
        self,
        source_id: str,
        user: UniversalObject,
        storage: FileStorage,
        *,
        limit: int = _DEFAULT_LIMIT,
    ) -> RelatedDocumentsResult:
        limit = max(1, min(int(limit), _MAX_LIMIT))

        # 1. Load + verify the source object exists.
        source = self._repository.get_by_id(ObjectId(source_id))
        if source is None:
            raise ObjectNotFoundError(f"Source document not found: {source_id}")

        # 2. READ permission on the source (before loading/embedding its text).
        principal = {"sub": str(user.id), "roles": get_roles(user)}
        if not self._permission_evaluator.can(
            principal=principal,
            scope=object_acl_scope(source),
            action=PermissionAction.READ,
        ):
            raise PermissionDeniedError(
                f"User lacks READ permission on source document {source_id}."
            )

        # M13.3.1 (defect-2 fix): related documents are a document-to-document
        # capability. The source must be a document (READ is checked first so
        # the type of an unauthorized object is never leaked).
        if source.object_type is not ObjectType.DOCUMENT:
            raise ValidationError(
                f"Source object {source_id} is not a document; related "
                f"documents require a document source."
            )

        # 3. Authoritative source text (existing intake pipeline).
        extraction = self._annotation_service.extracted_text(source_id, storage)
        if extraction is None or not extraction.get("text"):
            raise ValidationError(
                f"No extracted text available for source document {source_id}."
            )
        text = str(extraction["text"])

        # 4. Semantic search via the existing embedder + vector repository.
        #    Honest degradation: no backend, or any failure → empty results.
        if self._vector_repository is None or self._embedder is None:
            return RelatedDocumentsResult()
        try:
            query_vector = self._embedder.embed(text)
            # Fetch one extra so excluding the source cannot shrink the page.
            candidates = self._vector_repository.search(
                query_vector, limit=limit + 1
            )
        except Exception:  # noqa: BLE001 — embedding/search must never crash
            return RelatedDocumentsResult()

        # 5. Permission-filter (the authoritative R4 gate) + self-exclusion.
        return RelatedDocumentsResult(
            items=self._select(candidates, principal, str(source.id), limit)
        )

    # ------------------------------------------------------------- helpers
    def _select(
        self,
        candidates: list,
        principal: dict,
        source_id: str,
        limit: int,
    ) -> tuple[RelatedDocumentItem, ...]:
        """Authorize each candidate against the authoritative object, drop the
        source itself, and cap at ``limit``. Order/score follow the existing
        vector-search rank (cosine similarity), scored with the existing RRF
        convention. Stale index rows (object deleted) never leak."""
        objects = self._repository.find_by_ids(
            [ObjectId(c.object_id) for c in candidates]
        )
        by_id = {str(obj.id): obj for obj in objects}
        items: list[RelatedDocumentItem] = []
        for rank, candidate in enumerate(candidates):
            if len(items) >= limit:
                break
            cid = candidate.object_id
            if cid == source_id:
                continue  # the source is never related to itself
            obj = by_id.get(cid)
            if obj is None:
                continue  # index row for a deleted object — never leak
            if obj.object_type is not ObjectType.DOCUMENT:
                continue  # M13.3.1: related results are documents only
            if not self._permission_evaluator.can(
                principal=principal,
                scope=object_acl_scope(obj),
                action=PermissionAction.READ,
            ):
                continue  # semantically similar but not readable — drop
            items.append(
                RelatedDocumentItem(
                    object_id=cid,
                    object_type=candidate.object_type,
                    title=candidate.title,
                    version=candidate.version,
                    score=round(1.0 / (_RRF_K + rank + 1), _SCORE_DECIMALS),
                )
            )
        return tuple(items)


__all__ = ["RelatedDocumentsUseCase"]
