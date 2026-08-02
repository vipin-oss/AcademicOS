"""Boundary command: Create a Purchase Proposal."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.finance import CreateProposalInput


@dataclass
class CreateProposalCommand:
    input: CreateProposalInput
