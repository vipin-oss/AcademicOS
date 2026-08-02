"""Boundary query: Get one Committee by id (enriched workspace read)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GetCommitteeQuery:
    object_id: str
