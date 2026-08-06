"""Assistant Retrieval Service (Sprint-6 M1).

Pure application service — no prompt construction, no provider calls, no
streaming. It composes the TWO existing retrieval engines, both already
permission-filtered through the SAME R4 evaluator:

- **Hybrid search** — ``SearchObjectsUseCase`` (Sprint-5 M2): lexical +
  semantic candidates, reciprocal-rank fusion, deterministic ordering,
  R4 READ gate per candidate (unauthorized items never leak).
- **Graph runtime** — ``GraphRuntimeService`` (Sprint-2 M2): BFS traversal
  with the same R4 READ pre-filter, bounded by MAX_DEPTH/MAX_NODES.

Merge contract (deterministic):

1. Search hits first, in their RRF order (score desc, object_id asc).
2. Graph neighbours after, in BFS discovery order, anchored at the top
   search hits (related-object discovery).
3. Duplicates are eliminated by object_id keeping the FIRST occurrence; an
   item found by both legs reports ``sources=("search", "graph")``.
4. ``max_results`` bounds the merged list.

Permission filtering is NOT duplicated here: both consumers already apply
the existing ``ObjectPermissionEvaluator`` gate (search use case and graph
runtime), so every merged item has passed it. The service only composes.
"""
from __future__ import annotations

from app.application.dtos.assistant import (
    AssistantRetrievalResult,
    RetrievedItem,
)
from app.application.services.graph_runtime import GraphRuntimeService
from app.application.use_cases.auth.helpers import get_roles
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.domain.entities.object import UniversalObject
from app.domain.value_objects.object_id import ObjectId

# Defaults: bounded, CI-safe, aligned with the search route's limits.
DEFAULT_SEARCH_LIMIT = 8
DEFAULT_GRAPH_ANCHORS = 3
DEFAULT_GRAPH_DEPTH = 2
DEFAULT_MAX_RESULTS = 15


class AssistantRetrievalService:
    """Merges hybrid-search and graph-runtime results for one question."""

    def __init__(
        self,
        search: SearchObjectsUseCase,
        graph: GraphRuntimeService,
    ) -> None:
        self._search = search
        self._graph = graph

    def retrieve(
        self,
        query: str,
        user: UniversalObject,
        *,
        search_limit: int = DEFAULT_SEARCH_LIMIT,
        graph_anchors: int = DEFAULT_GRAPH_ANCHORS,
        graph_depth: int = DEFAULT_GRAPH_DEPTH,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> AssistantRetrievalResult:
        """Merged, deduplicated, deterministically ordered retrieval.

        ``user`` is the authenticated principal (its READ permissions gate
        both legs inside the reused consumers).
        """
        hits = self._search.execute(user=user, text=query, limit=search_limit)
        graph_items = self._graph_items(
            hits, user, anchors=graph_anchors, depth=graph_depth
        )
        return AssistantRetrievalResult(
            items=tuple(self._merge(hits, graph_items, max_results)),
            search_count=len(hits),
            graph_count=len(graph_items),
        )

    # ------------------------------------------------------------- graph leg
    def _graph_items(
        self,
        hits,
        user: UniversalObject,
        *,
        anchors: int,
        depth: int,
    ) -> list[dict]:
        """BFS neighbours of the top search hits (related-object discovery).

        The graph runtime pre-filters every visited node through the same
        R4 evaluator, so graph items are READ-safe by construction.
        """
        principal = {"sub": str(user.id), "roles": get_roles(user)}
        collected: list[dict] = []
        seen: set[str] = set()
        for hit in hits[:anchors]:
            out = self._graph.traverse(
                ObjectId(hit.object_id),
                direction="outgoing",
                kind=None,
                depth=depth,
                mode="bfs",
                principal=principal,
            )
            for item in out["items"]:
                node_id = str(item["id"])
                if node_id in seen:
                    continue
                seen.add(node_id)
                collected.append(item)
        return collected

    # --------------------------------------------------------------- merge
    @staticmethod
    def _merge(hits, graph_items: list[dict], max_results: int) -> list[RetrievedItem]:
        """Search hits first (ranked), then graph nodes (BFS order).

        Dedupe by object_id keeping the first occurrence; items found by
        both legs carry both sources. Deterministic: no timestamps, no
        insertion-order dependence beyond the two fixed sequences.
        """
        merged: list[RetrievedItem] = []
        position_by_id: dict[str, int] = {}

        def _add(item: RetrievedItem) -> None:
            position_by_id[item.object_id] = len(merged)
            merged.append(item)

        for hit in hits:
            _add(
                RetrievedItem(
                    object_id=hit.object_id,
                    object_type=hit.object_type,
                    title=hit.title,
                    version=hit.version,
                    sources=("search",),
                    score=hit.score,
                )
            )
        for node in graph_items:
            node_id = str(node["id"])
            position = position_by_id.get(node_id)
            if position is not None:
                # Upgrade provenance: the item was found by both legs.
                existing = merged[position]
                merged[position] = RetrievedItem(
                    object_id=existing.object_id,
                    object_type=existing.object_type,
                    title=existing.title,
                    version=existing.version,
                    sources=("search", "graph"),
                    score=existing.score,
                )
                continue
            _add(
                RetrievedItem(
                    object_id=node_id,
                    object_type=str(node["object_type"]),
                    title=str(node["title"]),
                    version=0,  # graph nodes carry no version
                    sources=("graph",),
                    score=0.0,
                )
            )
        return merged[:max_results]


__all__ = [
    "AssistantRetrievalService",
    "DEFAULT_GRAPH_ANCHORS",
    "DEFAULT_GRAPH_DEPTH",
    "DEFAULT_MAX_RESULTS",
    "DEFAULT_SEARCH_LIMIT",
]
