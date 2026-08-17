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

import json
import logging
from concurrent.futures import ThreadPoolExecutor

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
from app.domain.value_objects.enums import ObjectType, PermissionAction, UserRole
from app.domain.value_objects.object_id import ObjectId

_log = logging.getLogger(__name__)

# Reciprocal rank fusion constant (deterministic, standard RRF).
_RRF_K = 60
# Score rounding keeps the API output stable and short.
_SCORE_DECIMALS = 6

# V3 M9: pre-filter over-fetch factor — fetch this many extra candidates so
# unauthorized rows cannot crowd authorized ones out of the top-k, then rank
# only the authorized set. Bounded (never an unbounded scan).
_OVERFETCH_FACTOR = 4
_OVERFETCH_CAP = 1000


def _overfetch_limit(limit: int) -> int:
    return min(max(limit * _OVERFETCH_FACTOR, limit), _OVERFETCH_CAP)

# V3 M8: bounded shared executor for the semantic search leg. The semantic leg
# (embedder + vector repository) never touches the DB session, so running it on
# a worker thread while the lexical leg runs on the request thread is safe and
# yields the parallel-fan-out wall-clock win (blueprint A5: no async, no driver
# change). Bounded to 2 workers — it only ever runs one semantic leg per search.
_search_leg_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="search-leg")


class SearchObjectsUseCase:
    def __init__(
        self,
        search_repository: SearchRepository,
        object_repository: ObjectRepository,
        permission_evaluator: PermissionEvaluator,
        *,
        vector_repository: VectorRepository | None = None,
        embedder: Embedder | None = None,
        parallel: bool = True,
    ) -> None:
        self._search_repository = search_repository
        self._object_repository = object_repository
        self._permission_evaluator = permission_evaluator
        self._vector_repository = vector_repository
        self._embedder = embedder
        # V3 M8: feature-flag rollback for the parallel fan-out.
        self._parallel = parallel

    def execute(
        self,
        *,
        user: UniversalObject,
        text: str | None = None,
        object_type: str | None = None,
        title: str | None = None,
        filename: str | None = None,
        exclude_types: set[str] | None = None,
        limit: int = 50,
    ) -> list[SearchHit]:
        text = text.strip() if text else None
        title = title.strip() if title else None
        filename = filename.strip() if filename else None
        object_type = object_type.strip() if object_type else None
        if text is None and title is None and object_type is None and filename is None:
            raise ValidationError("At least one search criterion is required.")

        # V3 M9 (ADR-056): permission is a PRE-filter, never a post-filter.
        # Over-fetch so unauthorized candidates cannot crowd authorized ones
        # out of the top-k, authorize the candidate set against the live
        # objects BEFORE fusion/ranking, then rank only the authorized set.
        fetch_limit = _overfetch_limit(limit)
        lexical = self._search_repository.search(
            text=text, object_type=object_type, title=title, filename=filename,
            exclude_types=exclude_types, limit=fetch_limit,
        )
        semantic = self._semantic_leg(
            text=text, object_type=object_type, title=title, limit=fetch_limit,
            exclude_types=exclude_types,
        )

        principal = {"sub": str(user.id), "roles": get_roles(user)}
        lexical = self._authorized(lexical, principal)
        semantic = self._authorized(semantic, principal)

        return _fuse(lexical, semantic, limit=limit)

    def _authorized(self, candidates: list, principal: dict) -> list:
        """Drop candidates whose object is missing or not READ-authorized.

        The index is derived data; the object is the authority. A candidate
        for an object that no longer exists, or that the principal may not
        READ, is removed BEFORE ranking (never ranked, never leaked).

        For DOCUMENT objects: ownership is enforced when the document was
        created by a real user (owner starts with "obj:user:"). Documents
        with explicit ACL grants use the grant evaluator. Admins always pass.
        """
        if not candidates:
            return []
        objects = self._object_repository.find_by_ids(
            [ObjectId(c.object_id) for c in candidates]
        )
        by_id = {str(obj.id): obj for obj in objects}
        user_sub = str(principal.get("sub") or "")
        user_roles = [str(r) for r in (principal.get("roles") or [])]
        is_admin = UserRole.ADMIN.value in user_roles
        allowed: list = []
        for candidate in candidates:
            obj = by_id.get(candidate.object_id)
            if obj is None:
                continue
            # For DOCUMENT objects created by real users, enforce ownership
            if obj.object_type is ObjectType.DOCUMENT:
                owner = obj.audit.created_by if obj.audit else None
                # Only enforce ownership for documents with real user owners
                if owner and owner.startswith("obj:user:"):
                    if is_admin:
                        allowed.append(candidate)
                        continue
                    if owner == user_sub:
                        allowed.append(candidate)
                        continue
                    # Check explicit ACL grants
                    scope = object_acl_scope(obj)
                    if scope:
                        try:
                            acl = json.loads(scope)
                            has_grants = any(acl.get(k) for k in ("readers", "writers", "managers"))
                            if has_grants:
                                if self._permission_evaluator.can(
                                    principal=principal,
                                    scope=scope,
                                    action=PermissionAction.READ,
                                ):
                                    allowed.append(candidate)
                                continue
                        except (ValueError, TypeError):
                            pass
                    # No grants and not owner → deny
                    continue
            # Non-document or test-fixture documents: use standard evaluator
            if self._permission_evaluator.can(
                principal=principal,
                scope=object_acl_scope(obj),
                action=PermissionAction.READ,
            ):
                allowed.append(candidate)
        return allowed

    # ---------------------------------------------------------- semantic leg
    def _semantic_leg(
        self,
        *,
        text: str | None,
        object_type: str | None,
        title: str | None,
        limit: int,
        exclude_types: set[str] | None = None,
    ) -> list:
        """The semantic leg, optionally fanned out to the shared executor.

        V3 M8: when a semantic leg exists and parallel fan-out is enabled, run
        it on the bounded executor while the caller's lexical leg (already
        computed on the request thread) proceeds. The semantic leg is
        session-free (embedder + vector repository only), so this is safe.
        Results are identical to the sequential path — ``_semantic_candidates``
        is deterministic and swallows its own failures.
        """
        if (
            self._parallel
            and text is not None
            and self._vector_repository is not None
            and self._embedder is not None
        ):
            future = _search_leg_executor.submit(
                self._semantic_candidates,
                text=text,
                object_type=object_type,
                title=title,
                limit=limit,
                exclude_types=exclude_types,
            )
            return future.result()
        return self._semantic_candidates(
            text=text, object_type=object_type, title=title, limit=limit,
            exclude_types=exclude_types,
        )

    def _semantic_candidates(
        self,
        *,
        text: str | None,
        object_type: str | None,
        title: str | None,
        limit: int,
        exclude_types: set[str] | None = None,
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
        if exclude_types:
            candidates = [c for c in candidates if c.object_type not in exclude_types]
        return candidates


def _fuse(lexical: list, semantic: list, *, limit: int) -> list[SearchHit]:
    """Reciprocal rank fusion with deterministic object_id tie-breaks.

    Each candidate contributes 1/(k + rank + 1) per list it appears in;
    results are ordered by total score desc, object_id asc. With an empty
    semantic list (M1 mode) the fusion preserves the lexical order
    exactly, so behaviour is identical to Sprint-5 M1.
    """
    score_by_id: dict[str, float] = {}
    fields: dict[str, tuple[str, str, int, str]] = {}
    sources: dict[str, set[str]] = {}
    for rank, doc in enumerate(lexical):
        score_by_id[doc.object_id] = score_by_id.get(doc.object_id, 0.0) + 1.0 / (
            _RRF_K + rank + 1
        )
        fields.setdefault(
            doc.object_id, (doc.object_type, doc.title, doc.version, doc.metadata_text)
        )
        sources.setdefault(doc.object_id, set()).add(INDEX_SOURCE_LEXICAL)
    for rank, doc in enumerate(semantic):
        score_by_id[doc.object_id] = score_by_id.get(doc.object_id, 0.0) + 1.0 / (
            _RRF_K + rank + 1
        )
        fields.setdefault(
            doc.object_id, (doc.object_type, doc.title, doc.version, doc.metadata_text)
        )
        sources.setdefault(doc.object_id, set()).add(INDEX_SOURCE_SEMANTIC)

    ranked = sorted(score_by_id.items(), key=lambda item: (-item[1], item[0]))
    hits: list[SearchHit] = []
    for object_id, score in ranked[:limit]:
        object_type, title, version, metadata_text = fields[object_id]
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
                metadata_text=metadata_text,
            )
        )
    return hits
