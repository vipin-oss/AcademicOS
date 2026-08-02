"""Boundary query: PART 8 asset register across all proposals."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ListAssetRegisterQuery:
    page: int = 1
    page_size: int = 50
    q: str | None = None          # token-AND over item_name/asset_id/serial/location
    category: str | None = None
    status: str | None = None
