"""L8 temporal resolution — deterministic, rules-based (ADR-043).

Implements the blueprint's A6.3 temporal resolution as a pure, deterministic
resolver: "last spring" / "this year" / "after 2023" / "as of 2024-03" →
an explicit ISO bound pair, without a calendar/event data model or a temporal
database.

Determinism: a pure function of the current UTC datetime and the input string.
Timezone: ``resolve_time_range`` takes an optional ``now`` (tz-aware) so callers
provide the system timezone; the default is UTC. Bounded, testable.

Filtering: ``within_range(obj_created_at, start, end)`` is a deterministic
predicate for constraining results by creation time (the object store's canonical
temporal signal).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_YEAR_RE = re.compile(r"^(19|20)\d{2}$")
_MONTH_RE = re.compile(r"^(19|20)\d{2}-(0[1-9]|1[0-2])$")

ISO_TZ = timezone.utc


def _now_utc() -> datetime:
    return datetime.now(ISO_TZ)


def resolve_time_range(
    raw: str | None, *, now: datetime | None = None
) -> tuple[datetime | None, datetime | None]:
    """Resolve a ``time_range`` string to (start, end) ISO-aware bounds.

    Supported forms (deterministic, bounded):
    - ``None`` / ``""``            → (None, None)  (unbounded)
    - ``"this year"``              → [Jan 1 this year, Jan 1 next year)
    - ``"last year"``              → [Jan 1 last year, Jan 1 this year)
    - ``"YYYY"``                   → [Jan 1 YYYY, Jan 1 YYYY+1)
    - ``"after YYYY"``             → [Jan 1 YYYY+1, None)
    - ``"before YYYY"``            → [None, Jan 1 YYYY)
    - ``"as of YYYY"``             → [None, Dec 31 YYYY 23:59:59.999999]
    - ``"YYYY-MM"``                → [first of month, first of next month)
    - ``"this month"``             → [first of current month, first of next month)
    - ``"last N years"`` (N in 1..9)→ [Jan 1 (now.year - N), Jan 1 now.year)
    Unknown forms → (None, None)  (unbounded; caller decides coverage).

    ``now`` defaults to UTC.
    """
    if now is None:
        now = _now_utc()
    if now.tzinfo is None:
        now = now.replace(tzinfo=ISO_TZ)
    text = (raw or "").strip().casefold()
    if not text:
        return (None, None)

    year = now.year
    # this year / last year
    if text == "this year":
        return (datetime(year, 1, 1, tzinfo=now.tzinfo), datetime(year + 1, 1, 1, tzinfo=now.tzinfo))
    if text == "last year":
        return (datetime(year - 1, 1, 1, tzinfo=now.tzinfo), datetime(year, 1, 1, tzinfo=now.tzinfo))
    # this month
    if text == "this month":
        start = datetime(year, now.month, 1, tzinfo=now.tzinfo)
        end = _next_month_start(now)
        return (start, end)

    # last N years
    m = re.match(r"^last ([1-9]) years?$", text)
    if m:
        n = int(m.group(1))
        return (
            datetime(year - n, 1, 1, tzinfo=now.tzinfo),
            datetime(year, 1, 1, tzinfo=now.tzinfo),
        )

    # YYYY
    if _YEAR_RE.match(text):
        y = int(text)
        return (datetime(y, 1, 1, tzinfo=now.tzinfo), datetime(y + 1, 1, 1, tzinfo=now.tzinfo))

    # after YYYY
    m = re.match(r"^after (19|20)\d{2}$", text)
    if m:
        y = int(m.group(0).split()[-1])
        return (datetime(y + 1, 1, 1, tzinfo=now.tzinfo), None)

    # before YYYY
    m = re.match(r"^before (19|20)\d{2}$", text)
    if m:
        y = int(m.group(0).split()[-1])
        return (None, datetime(y, 1, 1, tzinfo=now.tzinfo))

    # as of YYYY
    m = re.match(r"^as of (19|20)\d{2}$", text)
    if m:
        y = int(m.group(0).split()[-1])
        return (
            None,
            datetime(y, 12, 31, 23, 59, 59, 999999, tzinfo=now.tzinfo),
        )

    # YYYY-MM
    if _MONTH_RE.match(text):
        y, mo = int(text[:4]), int(text[5:7])
        start = datetime(y, mo, 1, tzinfo=now.tzinfo)
        return (start, _next_month_start(datetime(y, mo, 1, tzinfo=now.tzinfo)))

    return (None, None)


def _next_month_start(dt: datetime) -> datetime:
    if dt.month == 12:
        return datetime(dt.year + 1, 1, 1, tzinfo=dt.tzinfo)
    return datetime(dt.year, dt.month + 1, 1, tzinfo=dt.tzinfo)


def within_range(
    value: datetime | str | None,
    start: datetime | None,
    end: datetime | None,
) -> bool:
    """Deterministic predicate: does ``value`` fall in [start, end)?

    ``None`` bounds are open. A ``None`` value is NOT within any bounded range
    (missing temporal signal → not claimed to be in range).
    """
    if value is None:
        return start is None and end is None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return False
        value = parsed
    if value.tzinfo is None:
        value = value.replace(tzinfo=ISO_TZ)
    if start is not None and value < start:
        return False
    if end is not None and value >= end:
        return False
    return True


__all__ = [
    "ISO_TZ",
    "resolve_time_range",
    "within_range",
]
