"""Boundary query: List personal tasks (PART 3 filters + pagination)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ListTasksQuery:
    page: int = 1
    page_size: int = 20
    q: str | None = None             # token-AND haystack (title/description/tags)
    priority: str | None = None
    category: str | None = None
    completed: bool | None = None    # three-state
    pinned: bool | None = None
    overdue: bool | None = None
    due_from: str | None = None
    due_to: str | None = None
