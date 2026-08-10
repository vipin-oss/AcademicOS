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
from app.application.assistant.intents import normalize
from app.application.use_cases.auth.helpers import get_roles
from app.application.use_cases.search.search_objects import SearchObjectsUseCase
from app.domain.entities.object import UniversalObject
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType
from app.domain.value_objects.object_id import ObjectId

# Defaults: bounded, CI-safe, aligned with the search route's limits.
DEFAULT_SEARCH_LIMIT = 8
DEFAULT_GRAPH_ANCHORS = 3
DEFAULT_GRAPH_DEPTH = 2
DEFAULT_MAX_RESULTS = 15

# P0-1: query formulation vocabulary. Intent/filler words dropped before
# retrieval; domain nouns (research, project, grant, publication, ...) are
# intentionally KEPT because they match object titles in the projection.
_QUERY_STOPWORDS = frozenset(
    {
        "find", "search", "look", "lookup", "show", "list", "give", "tell",
        "summarize", "summarise", "compare", "explain", "describe",
        "latest", "recent", "recently", "last", "new", "newest",
        "first", "top", "two", "one", "both", "each",
        "my", "me", "the", "a", "an", "i", "we", "you", "your", "please",
        "can", "could", "do", "does", "did", "have", "has", "had", "want",
        "need", "know", "like", "what", "which", "who", "how", "where",
        "when", "why", "are", "is", "was", "were", "be", "of", "to", "in",
        "on", "for", "with", "about", "related", "containing", "information",
        "any", "all", "that", "this", "these", "those", "there", "it", "its",
        "them", "they", "then", "than", "also", "just", "only", "up",
    }
)

# P0-2: object types whose metadata must NOT be injected into the prompt.
# AI_CONVERSATION objects store full message transcripts in metadata and
# USER objects carry account internals — internal state, not academic
# evidence. Their titles may still appear; their metadata is suppressed.
_NO_METADATA_TYPES = frozenset({ObjectType.AI_CONVERSATION, ObjectType.USER})

# Topic markers: the retrieval term is the content AFTER the LAST marker.
_TOPIC_MARKERS = (
    "related to",
    "containing",
    "information about",
    "about",
    "for",
)


def formulate_query(question: str) -> str:
    """Deterministic natural-language -> retrieval-term formulation (P0-1).

    The lexical leg is a substring (LIKE) search: a raw question like
    "Find my research projects related to mathematics" matches nothing
    (measured). This extracts the most content-bearing single term:

    1. normalize (lowercase, collapse whitespace, strip punctuation) —
       reuses the assistant intent vocabulary;
    2. if a topic marker ("related to", "containing", "about", ...)
       is present, take the text after the LAST marker; otherwise take the
       whole normalized question;
    3. drop filler words; prefer the FIRST remaining content token after a
       marker, else the LAST content token of the question;
    4. fall back to the normalized question when nothing contentful remains
       (keyword queries pass through unchanged).

    Pure and deterministic — no model, no network.
    """
    norm = normalize(question or "")
    if not norm:
        return ""
    topic = norm
    marker_matched = False
    for marker in _TOPIC_MARKERS:
        idx = norm.rfind(marker)
        if idx >= 0:
            topic = norm[idx + len(marker):].strip()
            marker_matched = True
            break
    words = [w for w in topic.split() if w and w not in _QUERY_STOPWORDS]
    if words and marker_matched:
        # After a topic marker the FIRST content token is the topic
        # ("related to mathematics" -> "mathematics").
        return words[0]
    # No marker matched (or nothing contentful after it): the domain noun
    # usually sits at the END ("research grants" -> "grants",
    # "latest research project" -> "project") — use the last content
    # token of the whole question.
    all_words = [w for w in norm.split() if w and w not in _QUERY_STOPWORDS]
    if all_words:
        return all_words[-1]
    return norm


def _singularize(term: str) -> str:
    """Naive singular fallback for the LIKE leg: 'grants' -> 'grant'."""
    if len(term) > 3 and term.endswith("ies"):
        return term[:-3] + "y"
    if len(term) > 2 and term.endswith("es"):
        return term[:-2]
    if len(term) > 1 and term.endswith("s") and not term.endswith("ss"):
        return term[:-1]
    return term


class AssistantRetrievalService:
    """Merges hybrid-search and graph-runtime results for one question."""

    def __init__(
        self,
        search: SearchObjectsUseCase,
        graph: GraphRuntimeService,
        *,
        repository: ObjectRepository | None = None,
    ) -> None:
        self._search = search
        self._graph = graph
        # P0-2: optional object repository — enriches graph-only items with
        # their metadata so the LLM receives evidence beyond titles.
        self._repository = repository

    def retrieve(
        self,
        query: str,
        user: UniversalObject,
        *,
        object_type: str | None = None,
        search_limit: int = DEFAULT_SEARCH_LIMIT,
        graph_anchors: int = DEFAULT_GRAPH_ANCHORS,
        graph_depth: int = DEFAULT_GRAPH_DEPTH,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> AssistantRetrievalResult:
        """Merged, deduplicated, deterministically ordered retrieval.

        ``user`` is the authenticated principal (its READ permissions gate
        both legs inside the reused consumers). ``object_type`` (Sprint-8
        M1) narrows the search leg to one object type — the assistant
        memory recall uses it for conversations; ``None`` keeps the
        pre-M1 behavior (all types).

        P0-1: the search leg runs on the FORMULATED retrieval term (the raw
        natural-language question is a whole-phrase LIKE query that matches
        nothing — measured); the original question still anchors the graph
        leg and the prompt. A deterministic singular fallback retries once
        when the formulated term yields zero hits ("grants" -> "grant").
        """
        term = formulate_query(query)
        hits = self._search.execute(
            user=user, text=term, object_type=object_type, limit=search_limit
        )
        if not hits and term and term != query:
            singular = _singularize(term)
            if singular != term:
                hits = self._search.execute(
                    user=user, text=singular, object_type=object_type,
                    limit=search_limit,
                )
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
    def _merge(self, hits, graph_items: list[dict], max_results: int) -> list[RetrievedItem]:
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
                    metadata_text=(
                        hit.metadata_text
                        if hit.object_type not in _NO_METADATA_TYPES
                        else ""
                    ),
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
                    metadata_text=existing.metadata_text,
                )
                continue
            node_type = str(node["object_type"])
            _add(
                RetrievedItem(
                    object_id=node_id,
                    object_type=node_type,
                    title=str(node["title"]),
                    version=0,  # graph nodes carry no version
                    sources=("graph",),
                    score=0.0,
                    metadata_text=(
                        self._metadata_for(node_id)
                        if node_type not in _NO_METADATA_TYPES
                        else ""
                    ),
                )
            )
        return merged[:max_results]

    def _metadata_for(self, object_id: str) -> str:
        """P0-2: deterministic ``key: value`` metadata lines for a
        graph-only item (the same shape the search projection uses)."""
        if self._repository is None:
            return ""
        obj = self._repository.get_by_id(ObjectId(object_id))
        if obj is None:
            return ""
        entries = sorted(obj.metadata.entries, key=lambda e: e.key)
        return "\n".join(f"{e.key}: {e.value}" for e in entries)


__all__ = [
    "AssistantRetrievalService",
    "DEFAULT_GRAPH_ANCHORS",
    "DEFAULT_GRAPH_DEPTH",
    "DEFAULT_MAX_RESULTS",
    "DEFAULT_SEARCH_LIMIT",
]
