"""Boundary query: List Vendors (search + pagination)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ListVendorsQuery:
    page: int = 1
    page_size: int = 20
    q: str | None = None  # token-AND haystack (name/GST/PAN/contact)
