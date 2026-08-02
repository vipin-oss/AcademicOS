"""Boundary command: Delete a Purchase Proposal."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeleteProposalCommand:
    object_id: str
