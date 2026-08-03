"""Boundary query: Aggregated calendar window feed (PART 1 + PART 2)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GetCalendarFeedQuery:
    date_from: str
    date_to: str
    sources: tuple[str, ...] | None = None  # None = every PART 2 source
