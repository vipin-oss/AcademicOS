"""Boundary query: List Events (PART 10 search + filters + pagination)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ListEventsQuery:
    page: int = 1
    page_size: int = 20
    q: str | None = None            # token-AND haystack (title/code/organizer/…)
    event_type: str | None = None   # event_type vocab
    year: str | None = None         # calendar year of start_date, e.g. "2026"
    role: str | None = None         # participation role (PART 2 vocab)
    department: str | None = None
    organizer: str | None = None    # organizer / co-organizer fragment
    status: str | None = None       # event_status vocab
