"""Boundary query: Notification Center list (PART 4 states + filters)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ListNotificationsQuery:
    page: int = 1
    page_size: int = 20
    q: str | None = None
    state: str | None = None         # unread | read | pinned | archived | snoozed | all
    priority: str | None = None
    category: str | None = None
    source_module: str | None = None
    owner_user_id: str | None = None  # requesting principal (2026-09 audit follow-up)
