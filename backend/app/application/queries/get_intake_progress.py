"""Query (CQRS intent) for session progress."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GetIntakeProgressQuery:
    session_id: str
