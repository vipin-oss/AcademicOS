"""Query (CQRS intent) for one intake session."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GetIntakeSessionQuery:
    session_id: str
