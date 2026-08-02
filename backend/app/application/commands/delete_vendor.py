"""Boundary command: Delete a Vendor."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeleteVendorCommand:
    object_id: str
