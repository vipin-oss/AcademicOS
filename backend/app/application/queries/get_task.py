"""Boundary query: Get one personal task."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GetTaskQuery:
    object_id: str
