"""Deterministic intent parser for the Academic Intelligence Assistant.

Version 1 is entirely local: an ordered rule table of compiled regular
expressions over the normalized question. No probability, no external calls —
which is exactly what makes the module unit-testable end to end. The parser
NEVER touches the database; entity resolution (funder names, free-text
keywords) happens in the provider layer on top of the captured params.

Rule ordering IS the semantics — most specific patterns first, generic
fallbacks last. Unmatched questions degrade to ``knowledge_search`` with the
raw question as the query (never an error), mirroring the "reuse the existing
Knowledge Graph search" doctrine.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.application.dtos.assistant import (
    INTENT_ACTIVE_PROJECTS,
    INTENT_ATTENDANCE_BELOW,
    INTENT_BUDGET_REMAINING,
    INTENT_BUDGET_SUMMARY,
    INTENT_CERTIFICATES,
    INTENT_COMMITTEE_MEETINGS,
    INTENT_COMPLETED_PROJECTS,
    INTENT_CONFERENCE_PAPERS,
    INTENT_DOCUMENTS_BY_KEYWORD,
    INTENT_EVENTS_ATTENDED,
    INTENT_EVENTS_ORGANIZED,
    INTENT_GREETING,
    INTENT_HELP,
    INTENT_KNOWLEDGE_SEARCH,
    INTENT_LATEST_PUBLICATION,
    INTENT_MODULE_REPORT_SUMMARY,
    INTENT_MY_PUBLICATIONS,
    INTENT_PENDING_ACTIONS,
    INTENT_PENDING_ASSIGNMENTS,
    INTENT_PENDING_GRADING,
    INTENT_PENDING_ITEMS,
    INTENT_PENDING_PURCHASES,
    INTENT_PENDING_REPORTS,
    INTENT_PROJECTS_BY_FUNDER,
    INTENT_PUBLICATIONS_THIS_YEAR,
    INTENT_RECENT_DECISIONS,
    INTENT_RECENT_PROCUREMENTS,
    INTENT_REPORT_CATALOGUE,
    INTENT_RESEARCH_GRANTS,
    INTENT_TODAY_PLAN,
    INTENT_UPCOMING_CLASSES,
    INTENT_UPCOMING_DEADLINES,
    INTENT_UPCOMING_EVENTS,
    INTENT_UPCOMING_MEETINGS,
    REPORT_MODULES,
)


@dataclass
class ParsedQuestion:
    intent: str
    params: dict[str, object] = field(default_factory=dict)
    query: str = ""  # free text kept for knowledge_search / keyword intents


_WS_RE = re.compile(r"\s+")
_STRIP_RE = re.compile(r"[\s?!.,;:]+$")
_WORD = r"[a-z0-9&.'’%\- ]"
_MODULE_RE = "|".join(REPORT_MODULES)


def normalize(text: str) -> str:
    """lower + collapse whitespace + strip trailing punctuation (keep inner)."""
    lowered = text.strip().lower().replace("’", "'")
    lowered = _WS_RE.sub(" ", lowered)
    return _STRIP_RE.sub("", lowered)


def _percent(text: str, default: int) -> int:
    match = re.search(r"(\d{1,3})\s*%", text)
    if match:
        return min(100, max(1, int(match.group(1))))
    match = re.search(r"below\s+(\d{1,3})", text)
    if match:
        return min(100, max(1, int(match.group(1))))
    return default


def _after(trigger: str) -> object:
    """Param extractor: capture the words after ``trigger`` (e.g. 'funded by')."""

    def extractor(_norm: str, match: re.Match) -> dict[str, object]:
        value = (match.group(match.lastindex or 1) or "").strip()
        return {"keyword": value}

    return extractor


def _no_params(_norm: str, _match: re.Match) -> dict[str, object]:
    return {}


def _with_threshold(_norm: str, _match: re.Match) -> dict[str, object]:
    return {"threshold": _percent(_norm, 75)}


def _workshop_flag(_norm: str, _match: re.Match) -> dict[str, object]:
    return {"event_type": "workshop" if "workshop" in _norm else ""}


def _report_module(_norm: str, match: re.Match) -> dict[str, object]:
    module = (match.group(match.lastindex or 1) or "analytics").strip()
    if module in ("of", "for", "the"):
        module = "analytics"
    return {"module": module if module in REPORT_MODULES else "analytics"}


_LEADING_FILLER = ("show", "list", "all", "my", "the", "any", "me")


def clean_keyword(value: str) -> str:
    """Strip leading filler verbs/articles from a captured keyword phrase."""
    words = [w for w in value.split() if w and w not in _LEADING_FILLER] or value.split()
    return " ".join(words).strip()


def _search_query(_norm: str, match: re.Match) -> dict[str, object]:
    return {"query": (match.group(1) or "").strip()}


# ---------------------------------------------------------------------------
# Rule table — (intent, patterns, extractor). FIRST match wins.
# ---------------------------------------------------------------------------
Rule = tuple[str, tuple[re.Pattern, ...], object]

RULES: tuple[Rule, ...] = (
    # --- teaching -------------------------------------------------------
    (INTENT_ATTENDANCE_BELOW, (
        re.compile(rf"student{_WORD}*below{_WORD}*attendance"),
        re.compile(r"attendance\s+below"),
        re.compile(r"low\s+attendance"),
        re.compile(r"shortage\s+of\s+attendance"),
    ), _with_threshold),
    (INTENT_PENDING_GRADING, (
        re.compile(r"(pending|awaiting|left)\s+grading"),
        re.compile(r"grading\s+(pending|left|due)"),
        re.compile(r"(ungraded|unevaluated)\s+submission"),
        re.compile(r"submissions?\s+(to|pending)\s+grade"),
        re.compile(r"(evaluate|grade)\s+pending\s+submissions?"),
    ), _no_params),
    (INTENT_PENDING_ASSIGNMENTS, (
        re.compile(r"assignments?\s+(pending|due)"),
        re.compile(r"(pending|due|upcoming)\s+assignments?"),
        re.compile(r"assignments?\s+to\s+(complete|submit|grade)"),
    ), _no_params),
    (INTENT_UPCOMING_CLASSES, (
        re.compile(r"(upcoming|next|todays?|today's)\s+classes"),
        re.compile(r"classes\s+(today|tomorrow|this\s+week)"),
        re.compile(r"my\s+(class|teaching)\s+schedule"),
    ), _no_params),
    # --- reports (before research: "publications report" must not hit
    # my_publications) ---------------------------------------------------
    (INTENT_MODULE_REPORT_SUMMARY, (
        re.compile(rf"summari[sz]e\s+(the\s+)?({_MODULE_RE})\s+report"),
        re.compile(rf"({_MODULE_RE})\s+report\s+summ"),
        re.compile(rf"report\s+summ\w*\s+(of|for)\s+({_MODULE_RE})"),
        re.compile(rf"({_MODULE_RE})\s+(summary|overview)\s+report"),
    ), _report_module),
    (INTENT_REPORT_CATALOGUE, (
        re.compile(r"what\s+reports?"),
        re.compile(r"report\s+(catalogue|catalog|list|kinds)"),
        re.compile(r"(list|show|which)\s+reports?"),
        re.compile(r"reports?\s+(available|can\s+i\s+(see|generate))"),
    ), _no_params),
    # --- research -------------------------------------------------------
    (INTENT_LATEST_PUBLICATION, (
        re.compile(r"(latest|recent|newest|last)\s+publications?"),
        re.compile(r"my\s+(latest|recent|newest)\s+(paper|publication)"),
    ), _no_params),
    (INTENT_PUBLICATIONS_THIS_YEAR, (
        re.compile(r"publications?\s+(this|current)\s+year"),
        re.compile(r"(this|current)\s+year'?s?\s+publications?"),
        re.compile(r"papers?\s+(this|current)\s+year"),
    ), _no_params),
    (INTENT_CONFERENCE_PAPERS, (
        re.compile(r"conference\s+(papers?|publications?|presentations?)"),
        re.compile(r"(papers?|presentations?)\s+(in|at)\s+conferences?"),
        re.compile(r"conference\s+proceedings?"),
    ), _no_params),
    (INTENT_PROJECTS_BY_FUNDER, (
        re.compile(rf"projects?\s+funded\s+by\s+({_WORD}+?)\s*$"),
        re.compile(rf"funded\s+by\s+({_WORD}+?)\s*$"),
        re.compile(rf"({_WORD}+?)\s+funded\s+projects?\s*$"),
    ), _after("funded by")),
    (INTENT_COMPLETED_PROJECTS, (
        re.compile(r"(completed|closed|finished)\s+(research\s+)?projects?"),
        re.compile(r"projects?\s+(completed|closed|finished)"),
    ), _no_params),
    (INTENT_ACTIVE_PROJECTS, (
        re.compile(r"(active|ongoing|running|current)\s+(research\s+)?projects?"),
        re.compile(r"(research\s+)?projects?\s+(active|ongoing|running)"),
        re.compile(r"my\s+(research\s+)?projects?"),
        re.compile(r"^(show\s+)?research\s+projects?$"),
    ), _no_params),
    (INTENT_RESEARCH_GRANTS, (
        re.compile(r"(research\s+)?grants?(\s+sanctioned|\s+received)?\s*$"),
        re.compile(r"(my\s+)?funding\s+grants?"),
        re.compile(r"grants?\s+(of|with)\s+"),
    ), _no_params),
    (INTENT_MY_PUBLICATIONS, (
        re.compile(r"(my\s+)?publications?"),
        re.compile(r"(show|list)\s+(my\s+)?(papers?|publications?)"),
        re.compile(r"my\s+(research\s+)?(papers?|output)"),
    ), _no_params),
    (INTENT_DOCUMENTS_BY_KEYWORD, (
        re.compile(rf"({_WORD}+?)\s+documents?\s*$"),
        re.compile(rf"documents?\s+(for|about|on|tagged)\s+({_WORD}+?)\s*$"),
        re.compile(r"^(my\s+)?documents?$"),
    ), _after("documents")),
    # --- events ---------------------------------------------------------
    (INTENT_EVENTS_ATTENDED, (
        re.compile(r"events?\s+(i\s+)?attended"),
        re.compile(r"attended\s+events?"),
        re.compile(r"events?\s+i\s+have\s+attended"),
    ), _no_params),
    (INTENT_EVENTS_ORGANIZED, (
        re.compile(r"events?\s+(i\s+)?organiz(e|ed|sing)"),
        re.compile(r"organiz(e|ed)\s+events?"),
        re.compile(r"events?\s+i\s+(organized|conducted|hosted)"),
    ), _no_params),
    (INTENT_CERTIFICATES, (
        re.compile(r"certificates?(\s+(earned|received|issued))?"),
        re.compile(r"my\s+certificates?"),
    ), _no_params),
    (INTENT_UPCOMING_EVENTS, (
        re.compile(r"(upcoming|next)\s+(events?|workshops?|seminars?|conferences?)"),
        re.compile(r"(events?|workshops?)\s+(today|tomorrow|this\s+week|this\s+month)"),
        re.compile(r"^(show\s+)?events?$"),
    ), _workshop_flag),
    # --- committees -----------------------------------------------------
    (INTENT_PENDING_ACTIONS, (
        re.compile(r"(pending\s+)?(committee\s+)?action\s+items?"),
        re.compile(r"(pending|open)\s+(committee\s+)?actions?"),
        re.compile(r"committee\s+actions?\s+pending"),
        re.compile(r"(my\s+)?actionables?"),
    ), _no_params),
    (INTENT_COMMITTEE_MEETINGS, (
        re.compile(r"committee\s+meetings?"),
        re.compile(r"meetings?\s+of\s+(the\s+)?committee"),
        re.compile(r"(iqac|committee)\s+(upcoming\s+)?meetings?"),
    ), _no_params),
    (INTENT_RECENT_DECISIONS, (
        re.compile(r"(recent|latest|last)\s+decisions?"),
        re.compile(r"decisions?\s+(taken|made|recorded)"),
        re.compile(r"committee\s+decisions?"),
        re.compile(r"(meeting\s+)?minutes\s+decisions?"),
    ), _no_params),
    # --- finance --------------------------------------------------------
    (INTENT_PENDING_PURCHASES, (
        re.compile(r"(pending|open|ongoing)\s+(purchases?|procurements?)"),
        re.compile(r"(purchases?|procurements?)\s+(pending|in\s+process)"),
        re.compile(r"pending\s+(purchase\s+)?(orders?|proposals?|pos)"),
    ), _no_params),
    (INTENT_RECENT_PROCUREMENTS, (
        re.compile(r"(recent|latest|last)\s+(procurements?|purchases?|orders?)"),
        re.compile(r"(procurements?|purchases?)\s+(done|completed|recent)"),
    ), _no_params),
    (INTENT_BUDGET_SUMMARY, (
        re.compile(r"budget\s+(summary|overview|status|position)"),
        re.compile(r"(summari[sz]e|show)\s+(the\s+)?budget"),
        re.compile(r"grant\s+budget"),
    ), _no_params),
    (INTENT_BUDGET_REMAINING, (
        re.compile(r"(remaining|left)\s+(budget|funds?|amount)"),
        re.compile(r"(budget|funds?)\s+(remaining|left|balance)"),
        re.compile(r"how\s+much\s+(budget|money|funds?)"),
        re.compile(r"balance\s+(budget|funds?|grant)"),
    ), _no_params),
    # --- dashboard ------------------------------------------------------
    (INTENT_TODAY_PLAN, (
        re.compile(r"what\s+(should|shall)\s+i\s+do\s+today"),
        re.compile(r"(my\s+)?(day|today)'?s?\s+plan"),
        re.compile(r"what('s|\s+is)\s+(on|due)\s+today"),
        re.compile(r"plan\s+(for\s+)?today"),
        re.compile(r"today\s+agenda"),
    ), _no_params),
    (INTENT_PENDING_REPORTS, (
        re.compile(r"(pending|due|overdue)\s+reports?"),
        re.compile(r"reports?\s+(pending|due|to\s+submit)"),
        re.compile(r"report\s+deadlines?"),
    ), _no_params),
    (INTENT_PENDING_ITEMS, (
        re.compile(r"what('s|\s+is)\s+pending"),
        re.compile(r"(pending|outstanding)\s+(items?|work|stuff|things)"),
        re.compile(r"^(my\s+)?pendings?$"),
        re.compile(r"what\s+do\s+i\s+owe"),
    ), _no_params),
    (INTENT_UPCOMING_DEADLINES, (
        re.compile(r"(upcoming|next|this\s+week'?s?)\s+deadlines?"),
        re.compile(r"deadlines?\s+(today|tomorrow|this\s+week|soon)"),
        re.compile(r"(any|what)\s+deadlines?"),
    ), _no_params),
    (INTENT_UPCOMING_MEETINGS, (
        re.compile(r"(upcoming|next|today'?s?)\s+meetings?"),
        re.compile(r"meetings?\s+(today|tomorrow|this\s+week)"),
        re.compile(r"(any|what)\s+meetings?"),
    ), _no_params),
    # --- meta -----------------------------------------------------------
    (INTENT_GREETING, (
        re.compile(r"^(hi|hii+|hello|hey|namaste|good\s+(morning|afternoon|evening))[\s!.]*$"),
    ), _no_params),
    (INTENT_HELP, (
        re.compile(r"^(help|capabilities|what\s+can\s+you\s+do)$"),
        re.compile(r"what\s+can\s+you\s+(do|answer|help)"),
        re.compile(r"(how\s+do\s+i|how\s+to)\s+use\s+(you|this|the\s+assistant)"),
    ), _no_params),
    (INTENT_KNOWLEDGE_SEARCH, (
        re.compile(rf"^(?:search\s+(?:for\s+)?|find\s+|look\s*up\s+|lookup\s+)({_WORD}+?)\s*$"),
    ), _search_query),
)


def parse_question(text: str) -> ParsedQuestion:
    """Map a raw question onto one intent. Never raises, never errors out:
    unmatched questions fall back to a knowledge-graph search."""
    norm = normalize(text)
    if not norm:
        return ParsedQuestion(intent=INTENT_HELP)
    for intent, patterns, extractor in RULES:
        for pattern in patterns:
            match = pattern.search(norm)
            if match:
                params = extractor(norm, match) if callable(extractor) else {}
                if "keyword" in params:
                    params["keyword"] = clean_keyword(str(params["keyword"]))
                query = str(params.get("query") or params.get("keyword") or "")
                return ParsedQuestion(intent=intent, params=params, query=query or norm)
    return ParsedQuestion(intent=INTENT_KNOWLEDGE_SEARCH, params={"query": norm}, query=norm)
