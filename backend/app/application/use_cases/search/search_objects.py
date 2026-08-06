"""Use case: search objects through the persistent search projections (Sprint-5 M2).

Hybrid retrieval: lexical candidates (the M1 ``SearchRepository``) are
fused with semantic candidates (the ``VectorRepository`` nearest-neighbour
leg) via reciprocal rank fusion — deterministic scores, deterministic
``object_id`` tie-breaks, no ranking engine. Every fused candidate then
passes the SAME R4 permission gate as M1 (unchanged): the index is derived
data, the object is the authority — unauthorized items never leak through
either leg.

Graceful degradation (mandatory): when the semantic layer is unavailable
(no ``vector_repository``/``embedder`` wired, no free-text query, or the
vector store raising at query time), the result is exactly the M1 lexical
behaviour — same candidates, same ordering, same gate.
"""
from __future__ import annotations

import logging

from app.application.dtos.search import (
    INDEX_SOURCE_BOTH,
    INDEX_SOURCE_LEXICAL,
    INDEX_SOURCE_SEMANTIC,
    SearchHit,
)
from app.application.exceptions import ValidationError
from app.application.ports.embedder import Embedder
from app.application.ports.permission import PermissionEvaluator
from app.application.use_cases.auth.helpers import get_roles
from app.application.use_cases.object_acl import object_acl_scope
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.repositories.search_repository import SearchRepository
from app.domain.repositories.vector_repository import VectorRepository
from app.domain.value_objects.enums import PermissionAction
from app.domain.value_objects.object_id import ObjectId

_log = logging.getLogger(__name__)

# Reciprocal rank fusion constant (deterministic, standard RRF).
_RRF_K = 60
# Score rounding keeps the API output stable and short.
_SCORE_DECIMALS = 6


class SearchObjectsUseCase:
    def __init__(
        self,
        search_repository: SearchRepository,
        object_repository: ObjectRepository,
        permission_evaluator: PermissionEvaluator,
        *,
        vector_repository: VectorRepository | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self._search_repository = search_repository
        self._object_repository = object_repository
        self._permission_evaluator = permission_evaluator
        self._vector_repository = vector_repository
        self._embedder = embedder

    def execute(
        self,
        *,
        user: UniversalObject,
        text: str | None = None,
        object_type: str | None = None,
        title: str | None = None,
        limit: int = 50,
    ) -> list[SearchHit]:
        text = text.strip() if text else None
        title = title.strip() if title else None
        object_type = object_type.strip() if object_type else None
        if text is None and title is None and object_type is None:
            raise ValidationError("At least one search criterion is required.")

        lexical = self._search_repository.search(
            text=text, object_type=object_type, title=title, limit=limit
        )
        semantic = self._semantic_candidates(
            text=text, object_type=object_type, title=title, limit=limit
        )
        hits = _fuse(lexical, semantic, limit=limit)
        if not hits:
            return []

        # Authorize the candidate set through the R4 seam before returning
        # anything: the index is derived data, the object is the authority.
        # (Unchanged from Sprint-5 M1 — one gate for every candidate,
        # regardless of which leg produced it.)
        objects = self._object_repository.find_by_ids(
            [ObjectId(hit.object_id) for hit in hits]
        )
        by_id = {str(obj.id): obj for obj in objects}
        principal = {"sub": str(user.id), "roles": get_roles(user)}
        allowed: list[SearchHit] = []
        for hit in hits:
            obj = by_id.get(hit.object_id)
            if obj is None:
                # Index row for an object that no longer exists: never leak.
                continue
            if self._permission_evaluator.can(
                principal=principal,
                scope=object_acl_scope(obj),
                action=PermissionAction.READ,
            ):
                allowed.append(hit)
        return allowed

    # ---------------------------------------------------------- semantic leg
    def _semantic_candidates(
        self,
        *,
        text: str | None,
        object_type: str | None,
        title: str | None,
        limit: int,
    ) -> list:
        """Nearest neighbours for a free-text query, or ``[]`` when the
        semantic layer is unavailable (graceful degradation to M1)."""
        if (
            text is None
            or self._vector_repository is None
            or self._embedder is None
        ):
            return []
        try:
            query_vector = self._embedder.embed(text)
            candidates = self._vector_repository.search(query_vector, limit=limit)
        except Exception:  # noqa: BLE001 — semantic must never break search
            _log.warning(
                "Semantic search unavailable; falling back to lexical-only.",
                exc_info=True,
            )
            return []
        # Apply the approved criteria to the semantic leg (AND semantics).
        if object_type:
            candidates = [c for c in candidates if c.object_type == object_type]
        if title:
            candidates = [c for c in candidates if c.title.lower() == title.lower()]
        return candidates


def _fuse(lexical: list, semantic: list, *, limit: int) -> list[SearchHit]:
    """Reciprocal rank fusion with deterministic object_id tie-breaks.

    Each candidate contributes 1/(k + rank + 1) per list it appears in;
    results are ordered by total score desc, object_id asc. With an empty
    semantic list (M1 mode) the fusion preserves the lexical order
    exactly, so behaviour is identical to Sprint-5 M1.
    """
    score_by_id: dict[str, float] = {}
    fields: dict[str, tuple[str, str, int]] = {}
    sources: dict[str, set[str]] = {}
    for rank, doc in enumerate(lexical):
        score_by_id[doc.object_id] = score_by_id.get(doc.object_id, 0.0) + 1.0 / (
            _RRF_K + rank + 1
        )
        fields.setdefault(doc.object_id, (doc.object_type, doc.title, doc.version))
        sources.setdefault(doc.object_id, set()).add(INDEX_SOURCE_LEXICAL)
    for rank, doc in enumerate(semantic):
        score_by_id[doc.object_id] = score_by_id.get(doc.object_id, 0.0) + 1.0 / (
            _RRF_K + rank + 1
        )
        fields.setdefault(doc.object_id, (doc.object_type, doc.title, doc.version))
        sources.setdefault(doc.object_id, set()).add(INDEX_SOURCE_SEMANTIC)

    ranked = sorted(score_by_id.items(), key=lambda item: (-item[1], item[0]))
    hits: list[SearchHit] = []
    for object_id, score in ranked[:limit]:
        object_type, title, version = fields[object_id]
        source_set = sources[object_id]
        index_source = (
            INDEX_SOURCE_BOTH
            if source_set == {INDEX_SOURCE_LEXICAL, INDEX_SOURCE_SEMANTIC}
            else next(iter(source_set))
        )
        hits.append(
            SearchHit(
                object_id=object_id,
                object_type=object_type,
                title=title,
                version=version,
                index_source=index_source,
                score=round(score, _SCORE_DECIMALS),
            )
        )
    return hits
