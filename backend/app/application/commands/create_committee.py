"""Boundary command: Create a Committee."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.committee import CreateCommitteeInput


@dataclass
class CreateCommitteeCommand:
    input: CreateCommitteeInput
