"""Boundary query: List Committees (PART 9 search + filters + pagination)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ListCommitteesQuery:
    page: int = 1
    page_size: int = 20
    q: str | None = None           # token-AND haystack search
    committee_type: str | None = None
    department: str | None = None
    status: str | None = None
    chairperson: str | None = None  # chairperson/leadership member names
    meeting_year: int | None = None
