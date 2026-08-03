"""Boundary query: Unified Productivity search (PART 7)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProductivitySearchQuery:
    q: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    priority: str | None = None
    category: str | None = None
    source: str | None = None  # tasks | notifications | calendar
    limit: int = 30
