"""Boundary query: Get one personal calendar entry."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GetCalendarEntryQuery:
    object_id: str
