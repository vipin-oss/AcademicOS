"""Deterministic prose extraction (V3 ADR-068, enhanced Revision #4).

Supplements the "Label: value" extractor with natural-language patterns for
the phrasing used in real certificates, letters, and academic documents.

Patterns are anchored and honest: nothing is fabricated when a pattern does
not match. AI-assisted semantic extraction can layer on top of this when
available, but storage never depends on it.

Revision #4 additions:
- Acceptance letter patterns (manuscript title, journal, authors)
- Improved date extraction from prose
- Better handling of quoted titles
"""

from __future__ import annotations

import re

from app.application.services.value_normalizer import normalize_date

# --- Existing patterns ---

_CERTIFY_RE = re.compile(
    r"(?i:this is to certify that)\s+"
    r"((?i:Dr\.?|Prof\.?|Mr\.?|Mrs\.?|Ms\.?|Shri|Smt\.?)\s+[A-Z][a-z]*(?:\s+[A-Z][a-z]*)*)"
)
_ENTITLED_RE = re.compile(r'entitled\s+["\u201c\u2018]?([^"\u201d\u2019\n]+?)["\u201d\u2019]?\s+at', re.IGNORECASE)
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

# --- Revision #4: Acceptance letter patterns ---

# "your manuscript entitled \"Title\"" or "your paper entitled 'Title'"
# or "your manuscript entitled Title has been accepted"
_MANUSCRIPT_ENTITLED_RE = re.compile(
    r'(?i:your\s+(?:manuscript|paper|article|submission)\s+entitled\s+)'
    r'["\u201c\u2018]([^"\u201d\u2019]+)["\u201d\u2019]',
    re.IGNORECASE,
)

# "has been accepted for publication in <JOURNAL>"
_ACCEPTED_IN_RE = re.compile(
    r"(?i:accepted\s+(?:for\s+publication\s+)?in\s+)"
    r"(.+?)(?=\.|,|\s+under|\s+with|\s+manuscript|\s+reference|\s+please|\s+we\s+|$)",
    re.IGNORECASE,
)

# "Manuscript ID: EST-2025-4567" or "Reference: ABC-123"
_MANUSCRIPT_ID_RE = re.compile(
    r"(?i:(?:manuscript\s+(?:id|number)|reference\s+(?:number|id)|paper\s+id)\s*[:]\s*)(\S+)",
    re.IGNORECASE,
)

# "Dear Dr. Kumar" or "Dear Prof. Sharma"
_DEAR_RE = re.compile(
    r"(?i:dear\s+(?:Dr\.?|Prof\.?|Mr\.?|Mrs\.?|Ms\.?)\s+([A-Z][a-z]*(?:\s+[A-Z][a-z]*)*))",
    re.IGNORECASE,
)

# "written by A, B, and C" or "authored by A and B"
_AUTHORED_BY_RE = re.compile(
    r"(?i:(?:written|authored)\s+by\s+)(.+?)(?=\.|,|\s+has\s+been|\s+was\s+accepted|$)",
    re.IGNORECASE,
)

# Date patterns in prose: "on 15 March 2025" or "dated 2025-03-15"
_DATE_IN_PROSE_RE = re.compile(
    r"(?i:(?:on|dated?|dated:)\s+)"
    r"(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+(?:,?\s+\d{4})?|\d{4}-\d{1,2}-\d{1,2})",
    re.IGNORECASE,
)

# Date range patterns: "on 10-12 March 2025" or "on 10 to 12 March 2025"
_DATE_RANGE_RE = re.compile(
    r"(?i:on\s+)"
    r"(\d{1,2}(?:st|nd|rd|th)?(?:\s*[-–]\s*\d{1,2}(?:st|nd|rd|th)?)?\s+[A-Za-z]+(?:,?\s+\d{4})?)",
    re.IGNORECASE,
)

# "participated in the X" for certificate event titles
# Uses [\s\S] to match across newlines since event names often span multiple lines
_PARTICIPATED_IN_RE = re.compile(
    r"(?i:participated\s+in\s+the\s+)"
    r"([\s\S]+?)(?=\s+(?:held|organi[sz]ed|on\s+\d|from\s+\d)\b|[,.]|\s*$)",
    re.IGNORECASE,
)

# "attended the X" for certificate event titles
_ATTENDED_RE = re.compile(
    r"(?i:attended\s+the\s+)"
    r"([\s\S]+?)(?=\s+(?:held|organi[sz]ed|on\s+\d|from\s+\d)\b|[,.]|\s*$)",
    re.IGNORECASE,
)

# "Best regards, Editor" or "Sincerely, Editor-in-Chief"
_EDITOR_RE = re.compile(
    r"(?i:(?:best\s+regards|sincerely|regards|yours\s+(?:sincerely|faithfully)),?\s+)"
    r"(.+?)(?=\s*$|\n)",
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

    # --- Certificate patterns ---

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

    # --- Acceptance letter patterns (Revision #4) ---

    manuscript = _MANUSCRIPT_ENTITLED_RE.search(text)
    if manuscript:
        title = " ".join(manuscript.group(1).split())
        out.setdefault("publication_title", (title, manuscript.group(1).strip()))

    accepted_in = _ACCEPTED_IN_RE.search(text)
    if accepted_in:
        journal = " ".join(accepted_in.group(1).split())
        out.setdefault("journal_name", (journal, accepted_in.group(1).strip()))

    manuscript_id = _MANUSCRIPT_ID_RE.search(text)
    if manuscript_id:
        out.setdefault("manuscript_id", (manuscript_id.group(1).strip(), manuscript_id.group(0).strip()))

    dear = _DEAR_RE.search(text)
    if dear:
        name = " ".join(dear.group(1).split())
        # Only set if not already set by certify pattern
        out.setdefault("recipient", (name, dear.group(0).strip()))

    authored = _AUTHORED_BY_RE.search(text)
    if authored:
        authors = " ".join(authored.group(1).split())
        out.setdefault("authors", (authors, authored.group(1).strip()))

    editor = _EDITOR_RE.search(text)
    if editor:
        name = " ".join(editor.group(1).split())
        out.setdefault("editor_name", (name, editor.group(1).strip()))

    # Date extraction from prose
    date_match = _DATE_IN_PROSE_RE.search(text)
    if date_match:
        date_str = date_match.group(1).strip()
        normalized = normalize_date(date_str)
        if normalized:
            out.setdefault("acceptance_date", (normalized, date_str))

    # --- Certificate event title extraction ---

    # "participated in the International Conference on AI..."
    participated = _PARTICIPATED_IN_RE.search(text)
    if participated:
        event_name = " ".join(participated.group(1).split())
        out.setdefault("conference_name", (event_name, participated.group(0).strip()))

    # "attended the X"
    attended = _ATTENDED_RE.search(text)
    if attended:
        event_name = " ".join(attended.group(1).split())
        out.setdefault("conference_name", (event_name, attended.group(0).strip()))

    # Date range extraction: "on 10-12 March 2025"
    date_range = _DATE_RANGE_RE.search(text)
    if date_range:
        date_str = date_range.group(1).strip()
        normalized = normalize_date(date_str)
        if normalized:
            out.setdefault("start_date", (normalized, date_str))

    return out


__all__ = ["prose_fields"]
