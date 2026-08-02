"""Boundary command: Update a Purchase Proposal (partial, merge semantics)."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.finance import UpdateProposalInput


@dataclass
class UpdateProposalCommand:
    object_id: str
    input: UpdateProposalInput
