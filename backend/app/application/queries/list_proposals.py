"""Boundary query: List Purchase Proposals (PART 12 search + filters + pagination)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ListProposalsQuery:
    page: int = 1
    page_size: int = 20
    q: str | None = None               # token-AND haystack (number/title/purpose)
    vendor: str | None = None          # vendor id or name fragment
    project: str | None = None         # linked project id
    grant: str | None = None           # linked grant id
    status: str | None = None          # proposal_status vocab
    department: str | None = None
    financial_year: str | None = None  # Indian FY, e.g. "2026-27" (Apr-Mar)
