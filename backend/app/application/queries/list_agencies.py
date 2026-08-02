"""Query (CQRS intent) for listing Funding Agencies."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ListAgenciesQuery:
    """Intent to list Funding Agencies with pagination and optional search."""

    page: int = 1
    page_size: int = 50
    q: str | None = None
    status: str | None = None
