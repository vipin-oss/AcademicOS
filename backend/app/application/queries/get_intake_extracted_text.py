"""Query: fetch the raw extracted text of one intake item (M2)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GetIntakeExtractedTextQuery:
    session_id: str
    item_id: str
