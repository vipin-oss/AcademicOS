"""Boundary query: Get one Meeting by id (enriched workspace read)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GetMeetingQuery:
    meeting_id: str
