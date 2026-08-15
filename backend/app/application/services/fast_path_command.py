"""L4 deterministic fast-path keyword router (offline).

Maps a user question to a frozen fast-path command via a SMALL, deterministic
keyword table. This is NOT a phrase→intent patch-farm (it is the frozen
offline fallback ADR-020 mandates, and it cannot grow beyond the frozen
fast-path command set). It returns ``None`` when no fast-path command matches,
so the pipeline falls through to clarify/refuse.
"""

from __future__ import annotations

from app.application.services.fast_path import FAST_PATH_COMMANDS

#: Deterministic keyword → fast-path command. Bounded, tied to the frozen
#: command set; only used when the LLM planner is unavailable.
_KEYWORDS: dict[str, str] = {
    "how many": "count",
    "how much": "count",
    "count": "count",
    "list": "list",
    "show me": "list",
    "find": "search",
    "search": "search",
    "search for": "search",
    "what": "lookup",
    "who": "lookup",
    "timeline": "timeline",
    "when": "timeline",
    "inventory": "inventory",
    "summar": "summarize",
    "summarize": "summarize",
    "compare": "compare",
    "aggregate": "aggregate",
    "total": "aggregate",
    "filter": "filter",
}


def match_fast_path(question: str) -> str | None:
    """Return the frozen fast-path command for ``question``, or None."""
    q = (question or "").casefold()
    for keyword, command in _KEYWORDS.items():
        if keyword in q and command in FAST_PATH_COMMANDS:
            return command
    return None


__all__ = ["match_fast_path"]
