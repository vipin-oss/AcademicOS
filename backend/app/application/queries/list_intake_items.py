"""Query (CQRS intent) for the paginated items of one session."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ListIntakeItemsQuery:
    session_id: str
    page: int = 1
    page_size: int = 50
