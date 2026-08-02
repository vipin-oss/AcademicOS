"""Boundary command: Update a Vendor (partial, merge semantics)."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.finance import UpdateVendorInput


@dataclass
class UpdateVendorCommand:
    object_id: str
    input: UpdateVendorInput
