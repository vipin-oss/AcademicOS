"""Boundary query: Reminder engine buckets (PART 5)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GetRemindersQuery:
    as_of: str | None = None  # testing seam; server defaults to today
