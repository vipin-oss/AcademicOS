"""Deterministic value normalization + validation (V3 ADR-067).

Deterministic-first: dates, DOIs, emails, URLs, currency amounts and plain
identifiers are normalized WITHOUT any model. Each normalizer returns either a
normalized value or ``None`` (unparseable -> the field is reported as
unresolved, never fabricated). The original source text is always retained
separately for provenance.
"""

from __future__ import annotations

import re
from datetime import date as _date

_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"https?://[^\s<>\"']+")
_AMOUNT_RE = re.compile(
    r"(?:₹|rs\.?|inr)\s?([0-9][0-9,]*(?:\.[0-9]+)?)", re.IGNORECASE
)
_NUMBER_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)")

#: Month names -> numeric (deterministic; English months used in Indian
#: administrative documents).
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_DAY_MONTH_YEAR = re.compile(
    r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)(?:,|\s+)?\s+(\d{4})"
)
_YEAR_MONTH_DAY = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")


def normalize_date(text: str | None) -> str | None:
    """Normalize a date string to ISO ``YYYY-MM-DD``, or None.

    Handles ``YYYY-MM-DD`` and ``D Month YYYY`` / ``D-Mon-YYYY``. Impossible
    dates (month > 12, day > 31, Feb 30, ...) return None.
    """
    if not text:
        return None
    s = text.strip()
    m = _YEAR_MONTH_DAY.search(s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return _date(y, mo, d).isoformat()
        except ValueError:
            return None
    m = _DAY_MONTH_YEAR.search(s)
    if m:
        d = int(m.group(1))
        mo = _MONTHS.get(m.group(2).lower())
        y = int(m.group(3))
        if mo is None:
            return None
        try:
            return _date(y, mo, d).isoformat()
        except ValueError:
            return None
    return None


def normalize_doi(text: str | None) -> str | None:
    if not text:
        return None
    m = _DOI_RE.search(text)
    return m.group(0).rstrip(".,;") if m else None


def normalize_email(text: str | None) -> str | None:
    if not text:
        return None
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else None


def normalize_url(text: str | None) -> str | None:
    if not text:
        return None
    m = _URL_RE.search(text)
    return m.group(0).rstrip(".,;)") if m else None


def normalize_amount(text: str | None) -> float | None:
    """Currency amount -> float (INR/₹/Rs). Returns None when unparseable.

    Strict: requires a currency marker so a bare year/identifier ("SERB/2024")
    is never mistaken for a money amount.
    """
    if not text:
        return None
    if isinstance(text, int | float) and not isinstance(text, bool):
        return float(text)
    m = _AMOUNT_RE.search(str(text))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def normalize_number(text: str | None) -> float | None:
    if not text:
        return None
    if isinstance(text, int | float) and not isinstance(text, bool):
        return float(text)
    m = _NUMBER_RE.search(str(text).replace(",", ""))
    if not m:
        return None
    val = float(m.group(1))
    # Reject values that look like calendar years (1900-2100) when they appear
    # in a context where a year doesn't make sense (e.g., duration in months).
    # This prevents "Year: 2025" from being extracted as duration_months=2025.
    if 1900 <= val <= 2100 and val == int(val):
        # Check if the text contains "year" or "month" context
        text_lower = str(text).lower()
        if "month" in text_lower or "duration" in text_lower or "period" in text_lower:
            # Context suggests duration, but value looks like a year — reject
            return None
    return val


def normalize_identifier(text: str | None) -> str | None:
    """A reference/certificate/order number: strip whitespace, uppercase for a
    canonical comparable form (used for duplicate detection)."""
    if not text:
        return None
    return " ".join(text.strip().split()).upper()


def normalize_text(text: str | None) -> str | None:
    """A plain text value: strip, collapse whitespace."""
    if not text:
        return None
    s = " ".join(str(text).strip().split())
    return s or None


def valid_date_range(start: str | None, end: str | None) -> bool:
    """True when the pair is a consistent interval (start <= end)."""
    if start is None or end is None:
        return True
    return start <= end


__all__ = [
    "normalize_amount",
    "normalize_date",
    "normalize_doi",
    "normalize_email",
    "normalize_identifier",
    "normalize_number",
    "normalize_text",
    "normalize_url",
    "valid_date_range",
]
