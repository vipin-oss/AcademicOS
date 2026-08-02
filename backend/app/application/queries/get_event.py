"""Boundary query: Get an Event (enriched workspace)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GetEventQuery:
    object_id: str
