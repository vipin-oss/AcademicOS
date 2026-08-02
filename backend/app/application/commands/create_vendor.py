"""Boundary command: Register a Vendor."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.finance import CreateVendorInput


@dataclass
class CreateVendorCommand:
    input: CreateVendorInput
