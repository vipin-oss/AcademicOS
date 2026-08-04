"""Query (CQRS intent) for the paginated session listing."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ListIntakeSessionsQuery:
    page: int = 1
    page_size: int = 20
