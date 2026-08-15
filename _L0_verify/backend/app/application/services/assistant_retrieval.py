"""Assistant Retrieval Service (Sprint-6 M1).

LEGACY / TRANSITIONAL (L0 freeze). ``retrieval_plan`` tables (stopwords,
domain nouns, topic markers, type-count markers, capitalized-common
words, document-ref regexes) are frozen. Question-specific vocabulary
changes are L0 violations. New language belongs in capability golden
sets, not here.

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

import re
from dataclasses import dataclass

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
        # Discourse openers: never retrieval terms, and never entities.
        # "According to the source text of ..." must not plan to "according".
        "according", "accordingly", "regarding", "concerning", "based",
        "given", "following", "respecting",
    }
)

# P0-2: object types whose metadata must NOT be injected into the prompt.
# AI_CONVERSATION objects store full message transcripts in metadata and
# USER objects carry account internals — internal state, not academic
# evidence. Their titles may still appear; their metadata is suppressed.
_NO_METADATA_TYPES = frozenset({ObjectType.AI_CONVERSATION, ObjectType.USER})

# AI-retrieval contamination fix: internal/system object types that must
# NEVER surface as AI evidence in GENERAL retrieval (object_type=None).
# AI_CONVERSATION objects are indexed in search_documents — their titles
# and stored messages are internal state, not academic knowledge — and
# USER objects carry account internals. The memory-recall path explicitly
# requests object_type=AI_CONVERSATION and is therefore NOT affected.
# Global search (SearchObjectsUseCase via GET /search) is untouched: this
# exclusion lives in the assistant retrieval service only.
_RETRIEVAL_EXCLUDED_TYPES = frozenset({ObjectType.AI_CONVERSATION, ObjectType.USER})

# P0 foundation: workflow-internal object types are NEVER academic evidence
# for general AI retrieval. INTAKE_ITEM/INTAKE_SESSION are staging/commit
# plumbing ("Folder import — Personal" sessions and their items must not
# surface as numbered AI sources); AI_CONVERSATION/USER carry internal
# state. The memory-recall path explicitly requests ai_conversation and is
# therefore exempt (caller-requested type bypasses the exclusion).
_AI_EVIDENCE_EXCLUDED_TYPES = _RETRIEVAL_EXCLUDED_TYPES | frozenset(
    {ObjectType.INTAKE_ITEM, ObjectType.INTAKE_SESSION}
)

#: Document filename/title pattern for the document-reference resolver:
#: a quoted string ending in a document extension (""Cblu Jan, 2024.pdf"").
_DOC_NAME_EXT = (
    r"\.(?:pdf|docx?|txt|md|markdown|csv|json|xlsx?|pptx?)\b"
)
_DOC_REF_QUOTED_RE = re.compile(
    r"[\"'\u201c\u201d\u2018\u2019]([^\"'\u201c\u201d\u2018\u2019]{1,160}?"
    + _DOC_NAME_EXT + r")[\"'\u201c\u201d\u2018\u2019]",
    re.IGNORECASE,
)
#: The LAST token of a filename: letters/digits/word-chars ending in an ext.
_DOC_REF_END_RE = re.compile(
    r"[\w’'.,&()\-]{1,80}\.(?:pdf|docx?|txt|md|markdown|csv|json|xlsx?|pptx?)$",
    re.IGNORECASE,
)

# Topic markers: the retrieval term is the content AFTER the LAST marker.
# Matching is WORD-BOUNDARY based (never substring): a bare "for" must not
# match inside "information" and turn the query into the fragment "mation".
_TOPIC_MARKERS = (
    "related to",
    "containing",
    "information about",
    "about",
    "for",
)

#: Capitalized words that are NOT entities — months, weekdays and date words.
#: Without this, "Which conference did I attend in January 2024?" treats
#: "January" as a proper noun and hijacks the type-scoped event search.
_CAPITALIZED_COMMON_WORDS = frozenset(
    {
        "january", "february", "march", "april", "may", "june", "july",
        "august", "september", "october", "november", "december",
        "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept",
        "oct", "nov", "dec",
        "monday", "tuesday", "wednesday", "thursday", "friday",
        "saturday", "sunday", "mon", "tue", "tues", "wed", "thu", "thur",
        "thurs", "fri", "sat", "sun",
        "today", "yesterday", "tomorrow",
    }
)

#: File extensions that mark a DOCUMENT-REFERENCE query ("from Cblu Jan,
#: 2024.pdf"). Such queries may name the document at sentence start, so a
#: sentence-initial capitalized token is then a trustworthy entity signal.
_DOC_REF_EXTENSIONS = (
    ".pdf", ".docx", ".doc", ".txt", ".md", ".markdown", ".csv",
    ".json", ".xlsx", ".xls", ".pptx", ".ppt",
)


# ---------------------------------------------------------------------------
# Multi-signal retrieval plan (evidence-based fix, second forensic analysis)
# ---------------------------------------------------------------------------
# A single "last content token" loses information (Hindi auxiliaries, verbs,
# years, proper nouns). The plan extracts up to three signals, in priority
# order, and reuses the EXISTING object_type-scoped search seam:
#   A. topic markers      -> existing marker behavior (formulate_query),
#                           matched as WHOLE WORDS ("for" cannot fire
#                           inside "information")
#   B. proper nouns       -> the meaningful entity (CBLU), not "attended";
#                           months/weekdays excluded; sentence-initial
#                           entities accepted only for document references
#   C. year + domain noun -> type + year constraint ("papers ... in 2025")
#   D. type/count question-> object_type-scoped search (text optional)
#   E. domain noun        -> text + object_type
#   F. fallback           -> existing last-content-token behavior (unchanged)


@dataclass(frozen=True)
class RetrievalPlan:
    """Deterministic retrieval signals for one question.

    ``terms`` are tried in order (first non-empty hit set wins); ``object_type``
    narrows the search leg when set; ``type_question`` allows a final
    no-text type-scoped search (e.g. "how many publications do I have").
    """

    terms: tuple[str, ...] = ()
    object_type: str | None = None
    type_question: bool = False
    # P0: a document-reference intent ("According to the source text of
    # "Cblu Jan, 2024.pdf" ..."). When set, retrieval must FIRST resolve the
    # referenced document by exact filename/title; the evidence gate then
    # requires it to be present with source text before an answer is allowed.
    document_ref: str | None = None


#: Domain nouns -> existing ObjectType values (exact enum names).
_DOMAIN_NOUN_TO_TYPE: dict[str, ObjectType] = {
    "publication": ObjectType.PUBLICATION,
    "publications": ObjectType.PUBLICATION,
    "paper": ObjectType.PUBLICATION,
    "papers": ObjectType.PUBLICATION,
    "grant": ObjectType.GRANT,
    "grants": ObjectType.GRANT,
    "conference": ObjectType.EVENT,
    "conferences": ObjectType.EVENT,
    "event": ObjectType.EVENT,
    "events": ObjectType.EVENT,
    "project": ObjectType.RESEARCH_PROJECT,
    "projects": ObjectType.RESEARCH_PROJECT,
    "document": ObjectType.DOCUMENT,
    "documents": ObjectType.DOCUMENT,
    "designation": ObjectType.FACULTY,
}

#: Type/count question markers (normalized form).
_TYPE_COUNT_MARKERS = ("how many", "total number of", "number of", "which", "what")

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _marker_at(norm: str) -> tuple[str, int] | None:
    """The first topic marker present as a WHOLE WORD: ``(marker, start)``.

    Word-boundary matching is mandatory: a bare ``"for"`` occurs inside
    ``"information"`` as a substring but never as a word, so it cannot
    fire and slice the query into ``"mation"``.
    """
    for marker in _TOPIC_MARKERS:
        match = re.search(rf"\b{re.escape(marker)}\b", norm)
        if match is not None:
            return marker, match.start()
    return None


def _marker_last_index(norm: str, marker: str) -> int | None:
    """Start index of the LAST whole-word occurrence of ``marker``."""
    matches = list(re.finditer(rf"\b{re.escape(marker)}\b", norm))
    if not matches:
        return None
    return matches[-1].start()


def _proper_noun(question: str, norm: str) -> str | None:
    """A capitalized token that is a real entity (proper noun), or ``None``.

    Exclusions (deterministic, no NLP stack):
    - question/imperative words at sentence start (already in the stopword
      set: ``What/When/Tell/Find/...``) and discourse openers
      (``According/Regarding/...`` — also in the stopword set);
    - capitalized COMMON words anywhere — ``January`` is a month, not the
      entity, so the domain-noun branch can scope the type correctly;
    - sentence-initial tokens UNLESS the token itself begins a document
      name: it carries a file extension (``Cblu.pdf``), or the next
      significant token is a capitalized month/weekday or a 4-digit year
      (``Cblu Jan 2024``, ``Cblu Jan, 2024.pdf``, ``Cblu 2024``). This
      keeps ``Cblu Jan 2024`` -> ``cblu`` while ``According to the source
      text of "Cblu Jan, 2024.pdf" ...`` -> ``cblu`` (never ``according``)
      and Hinglish ``Maine CBLU me ...`` ("I ...") -> ``cblu`` (never
      ``maine``).
    """
    tokens = (question or "").split()
    for idx, token in enumerate(tokens):
        stripped = token.strip("'\".,!?;:’‘")
        if len(stripped) <= 1:
            continue
        if not (stripped[0].isupper() and stripped[0].isalpha()):
            continue
        lowered = stripped.lower()
        if lowered in _CAPITALIZED_COMMON_WORDS:
            continue
        if lowered in _QUERY_STOPWORDS:
            continue
        if idx == 0 and not _starts_document_name(tokens, idx):
            # Sentence-initial capitalized word that does not begin a
            # document name is a discourse opener or an imperative — not a
            # trustworthy entity (the real entity, if any, is mid-sentence
            # and found by the continuing scan).
            continue
        return lowered
    return None


def _starts_document_name(tokens: list[str], idx: int) -> bool:
    """Whether the token at ``idx`` begins a document-name pattern.

    True when the token itself carries a file extension (``Cblu.pdf``) or
    the next significant token is a capitalized month/weekday (``Cblu Jan
    2024``) or a 4-digit year (``Cblu 2024``). Discourse openers
    (``According to ...``, ``Maine CBLU ...``) fail every branch, so the
    sentence-initial gate keeps rejecting them.
    """
    current = tokens[idx].strip("'\".,!?;:’‘").lower()
    if current.endswith(_DOC_REF_EXTENSIONS):
        return True
    for nxt in tokens[idx + 1:idx + 3]:
        nxt_clean = nxt.strip("'\".,!?;:’‘")
        if not nxt_clean:
            continue
        if _YEAR_RE.fullmatch(nxt_clean):
            return True
        if nxt_clean.lower() in _CAPITALIZED_COMMON_WORDS and nxt_clean[0].isupper():
            return True
        break  # the first significant next token decides
    return False


def _domain_noun_type(norm: str) -> tuple[str | None, ObjectType | None]:
    """The LAST domain noun present in the normalized question."""
    words = norm.split()
    for word in reversed(words):
        obj_type = _DOMAIN_NOUN_TO_TYPE.get(word)
        if obj_type is not None:
            return word, obj_type
    return None, None


def _is_type_count_question(norm: str) -> bool:
    return any(marker in norm for marker in _TYPE_COUNT_MARKERS)


def _document_reference(question: str) -> str | None:
    """A document filename/title referenced in the question, or ``None``.

    P0 document-reference intent: the strongest signal in a query is an
    explicit file name (``"Cblu Jan, 2024.pdf"``, ``Cblu Jan, 2024.pdf``).
    Quoted references are matched first (unambiguous); otherwise the first
    bare filename is recovered by anchoring on a token that ends in a
    document extension and walking LEFT over capitalized/numeric name
    tokens (``Cblu Jan, 2024.pdf``), stopping at lower-case prose or
    sentence openers. A document extension is REQUIRED — prose ("the CBLU
    document") is not treated as a filename and flows through the normal
    intent branches.
    """
    if not question:
        return None
    quoted = _DOC_REF_QUOTED_RE.search(question)
    if quoted:
        return quoted.group(1).strip()
    tokens = (question or "").split()
    for index, token in enumerate(tokens):
        clean = token.strip("'\".,!?;:’‘()")
        if _DOC_REF_END_RE.search(clean):
            start = index
            while start > 0:
                prev = tokens[start - 1].strip("'\".,!?;:’‘()")
                if not prev:
                    break
                if prev[0].isupper() or prev[0].isdigit():
                    if prev.lower() not in _QUERY_STOPWORDS:
                        start -= 1
                        continue
                break
            span = tokens[start:index + 1]
            parts = [
                t.strip("'\".,!?;:’‘()") if k == len(span) - 1
                else t.lstrip("'\"(’‘")
                for k, t in enumerate(span)
            ]
            name = " ".join(parts).strip()
            if 3 <= len(name) <= 120:
                return name
            return None
    return None


def retrieval_plan(question: str) -> RetrievalPlan:
    """Deterministic multi-signal plan for one question (see module docs)."""
    norm = normalize(question or "")
    if not norm:
        return RetrievalPlan(terms=())

    # A0. DOCUMENT-REFERENCE intent — highest priority: the user names a
    #     specific file ("According to the source text of "Cblu Jan,
    #     2024.pdf" ..."). The plan resolves it by exact filename/title
    #     first; the evidence gate enforces it downstream.
    doc_ref = _document_reference(question)
    if doc_ref:
        return RetrievalPlan(terms=(doc_ref,), document_ref=doc_ref)

    # A. topic markers keep the existing marker behavior ("related to X"),
    #    matched as WHOLE WORDS — "for" inside "information" must never
    #    fire and reduce the query to "mation".
    if _marker_at(norm) is not None:
        return RetrievalPlan(terms=(formulate_query(question),))

    # B. proper noun / entity — preserve it instead of a verb/auxiliary.
    proper = _proper_noun(question, norm)
    if proper:
        return RetrievalPlan(terms=(proper,))

    # C/D/E. domain noun -> type (+ year / count handling).
    noun, obj_type = _domain_noun_type(norm)
    if noun and obj_type is not None:
        year_match = _YEAR_RE.search(norm)
        if year_match:
            # "which papers ... in 2025" -> type + year constraint.
            return RetrievalPlan(terms=(noun, year_match.group(0)), object_type=obj_type.value)
        if _is_type_count_question(norm):
            # "how many publications do I have" -> type-scoped (text optional).
            return RetrievalPlan(terms=(noun,), object_type=obj_type.value, type_question=True)
        return RetrievalPlan(terms=(noun,), object_type=obj_type.value)

    # F. fallback: existing behavior (unchanged).
    return RetrievalPlan(terms=(formulate_query(question),))


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
        idx = _marker_last_index(norm, marker)
        if idx is not None:
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
        # Multi-signal plan (evidence-based fix): document references,
        # proper nouns, domain nouns + object_type, year constraints and
        # type/count questions are extracted BEFORE the legacy single-token
        # fallback. Caller-supplied object_type (memory recall) always wins
        # over the plan's.
        plan = retrieval_plan(query)
        effective_type = object_type or plan.object_type
        resolved_id: str | None = None
        if plan.document_ref:
            # P0: document-reference intent — resolve the named file by
            # exact filename/title BEFORE any fuzzy term search.
            ref_hits = self._resolve_document_reference(
                plan.document_ref, user, search_limit
            )
            if ref_hits:
                resolved_id = ref_hits[0].object_id
                hits = ref_hits
            else:
                hits = self._search_by_plan(plan, user, effective_type, search_limit)
        else:
            hits = self._search_by_plan(plan, user, effective_type, search_limit)
        graph_items = self._graph_items(
            hits, user, anchors=graph_anchors, depth=graph_depth
        )
        merged = tuple(self._merge(hits, graph_items, max_results))
        return AssistantRetrievalResult(
            items=merged,
            search_count=len(hits),
            graph_count=len(graph_items),
            document_reference=plan.document_ref,
            document_reference_resolved=(
                resolved_id is not None
                and any(it.object_id == resolved_id for it in merged)
            ),
            resolved_document_id=resolved_id,
        )

    def _exclude_internal_types(self, hits, object_type: str | None):
        """Drop internal/workflow hits from AI retrieval.

        Workflow-internal types (AI_CONVERSATION, USER, INTAKE_ITEM,
        INTAKE_SESSION) are excluded UNLESS the caller explicitly requested
        one of them (the memory-recall path searches AI_CONVERSATION on
        purpose). A general type-scoped search (e.g. object_type=grant from
        the retrieval plan) still excludes internal objects — conversation
        content and intake plumbing can never become AI evidence or a cited
        source.
        """
        if not hits:
            return hits
        if object_type is not None and object_type in {
            t.value for t in _AI_EVIDENCE_EXCLUDED_TYPES
        }:
            return hits
        return [h for h in hits if h.object_type not in _AI_EVIDENCE_EXCLUDED_TYPES]

    def _exclude_set(self, object_type: str | None) -> set[str]:
        """The SQL-level exclusion set for one search leg.

        P0: exclusions are applied IN THE SQL WHERE clause (never after the
        limit), so internal/workflow objects cannot consume the candidate
        window and starve real evidence. A caller-requested excluded type
        (memory recall) is removed from the set for that leg.
        """
        excluded = {t.value for t in _AI_EVIDENCE_EXCLUDED_TYPES}
        if object_type in excluded:
            excluded = excluded - {object_type}
        return excluded

    def _resolve_document_reference(self, ref, user, search_limit):
        """Resolve a referenced document by EXACT filename, then EXACT title.

        Returns the first permission-filtered, non-internal hit set, or
        ``[]``. Variants tried: the reference verbatim (lowercased), then a
        punctuation-stripped variant ("Cblu Jan, 2024.pdf" ->
        "cblu jan 2024.pdf"). The exact filename lookup matches the
        ``file_name:`` metadata entry, so a user-entered title different
        from the file name is handled correctly.
        """
        variants = [ref.strip()]
        stripped = re.sub(r"[\u2019'’\"]", "", ref).replace(",", "").strip()
        if stripped.lower() != ref.lower():
            variants.append(stripped)
        excluded = self._exclude_set(None)
        for variant in variants:
            hits = self._search.execute(
                user=user, filename=variant, exclude_types=excluded,
                limit=search_limit,
            )
            hits = self._exclude_internal_types(hits, None)
            if hits:
                return hits
            hits = self._search.execute(
                user=user, title=variant, exclude_types=excluded,
                limit=search_limit,
            )
            hits = self._exclude_internal_types(hits, None)
            if hits:
                return hits
        return []

    def _search_by_plan(self, plan, user, object_type, search_limit):
        """Run the plan's term chain; each term + singular fallback, then a
        type-only search for type/count questions. Internal/workflow types
        are excluded at every step (in the SQL WHERE clause AND after the
        leg). Returns the first non-empty, permission-filtered hit set."""
        excluded = self._exclude_set(object_type)
        terms = list(plan.terms) or [""]
        for term in terms:
            hits = self._search.execute(
                user=user, text=term or None, object_type=object_type,
                exclude_types=excluded, limit=search_limit,
            )
            hits = self._exclude_internal_types(hits, object_type)
            if hits:
                return hits
            singular = _singularize(term) if term else term
            if singular and singular != term:
                hits = self._search.execute(
                    user=user, text=singular, object_type=object_type,
                    exclude_types=excluded, limit=search_limit,
                )
                hits = self._exclude_internal_types(hits, object_type)
                if hits:
                    return hits
        if plan.type_question and object_type is not None:
            # "how many publications do I have" -> all of the type.
            hits = self._search.execute(
                user=user, text=None, object_type=object_type,
                exclude_types=excluded, limit=search_limit,
            )
            hits = self._exclude_internal_types(hits, object_type)
            if hits:
                return hits
        return []

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
            if node_type in {t.value for t in _AI_EVIDENCE_EXCLUDED_TYPES}:
                continue  # internal/workflow objects never enter the merged result
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
