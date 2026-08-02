"""Boundary query: Get a Vendor."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GetVendorQuery:
    object_id: str
