"""Boundary query: List personal calendar entries."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ListCalendarEntriesQuery:
    page: int = 1
    page_size: int = 20
    q: str | None = None
    category: str | None = None
    date_from: str | None = None
    date_to: str | None = None
