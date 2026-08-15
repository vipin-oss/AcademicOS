"""Deterministic prose extraction (V3 ADR-068).

Supplements the "Label: value" extractor with natural-language patterns for
the phrasing used in real certificates and letters, so structured facts are
recovered WITHOUT explicit labels and WITHOUT an LLM:

- "This is to certify that <NAME> ..."                    -> recipient
- "presented a paper entitled '<T>'"                       -> presentation_title
- "at the International Conference <C>"                    -> conference_name
- "held at <VENUE> from <D1> to <D2>"                      -> venue + start/end date
- "organized by <ORG>"                                     -> conference_organizer
- "from <D1> to <D2>" (anywhere)                           -> start/end date

Deterministic and honest: patterns are anchored; nothing is fabricated when a
pattern does not match. AI-assisted semantic extraction can layer on top of
this when available (see ADR-068), but storage never depends on it.
"""

from __future__ import annotations

import re

from app.application.services.value_normalizer import normalize_date

_CERTIFY_RE = re.compile(
    r"(?i:this is to certify that)\s+"
    r"((?i:Dr\.?|Prof\.?|Mr\.?|Mrs\.?|Ms\.?|Shri|Smt\.?)\s+[A-Z][a-z]*(?:\s+[A-Z][a-z]*)*)"
)
_ENTITLED_RE = re.compile(r"entitled\s+[\"'“]?([^\"'”\n]+?)[\"'”]?\s+at", re.IGNORECASE)
_AT_CONFERENCE_RE = re.compile(
    r"at the\s+(?:international\s+|national\s+)?(?:conference|symposium|workshop|seminar)\s+(?:on\s+)?"
    r"(.+?)(?=\s+(?:organi[sz]ed|held|from|to)\b|[,.])",
    re.IGNORECASE,
)
_HELD_AT_RE = re.compile(r"held at\s+(.+?)(?=,|\.|\s+from\b|\s+to\b|$)", re.IGNORECASE)
_ORGANIZED_RE = re.compile(
    r"organi[sz]ed by\s+(.+?)(?=\s+(?:held|from|to)\b|[,.])", re.IGNORECASE
)
_FROM_TO_RE = re.compile(
    r"from\s+(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4}|\d{4}-\d{1,2}-\d{1,2})"
    r"\s+to\s+(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+\d{4}|\d{4}-\d{1,2}-\d{1,2})",
    re.IGNORECASE,
)


def _first(patterns: tuple[re.Pattern, ...], text: str) -> str | None:
    for p in patterns:
        m = p.search(text)
        if m:
            return " ".join(m.group(1).split())
    return None


def prose_fields(text: str) -> dict[str, tuple[str, str]]:
    """Return {predicate_id: (value, original_text)} from prose patterns."""
    out: dict[str, tuple[str, str]] = {}

    certify = _CERTIFY_RE.search(text)
    if certify:
        name = " ".join(certify.group(1).split())
        out.setdefault("recipient", (name, certify.group(1).strip()))

    entitled = _ENTITLED_RE.search(text)
    if entitled:
        out.setdefault("presentation_title", (entitled.group(1).strip(), entitled.group(1).strip()))

    conf = _AT_CONFERENCE_RE.search(text)
    if conf:
        name = conf.group(1).strip()
        out.setdefault("conference_name", (name, name))

    held = _HELD_AT_RE.search(text)
    if held:
        venue = held.group(1).strip()
        out.setdefault("venue", (venue, venue))

    organized = _ORGANIZED_RE.search(text)
    if organized:
        out.setdefault("conference_organizer", (organized.group(1).strip(), organized.group(1).strip()))

    span = _FROM_TO_RE.search(text)
    if span:
        start = normalize_date(span.group(1))
        end = normalize_date(span.group(2))
        if start:
            out.setdefault("start_date", (start, span.group(1).strip()))
        if end:
            out.setdefault("end_date", (end, span.group(2).strip()))

    return out


__all__ = ["prose_fields"]
