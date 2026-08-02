"""Boundary query: Get a Purchase Proposal (enriched workspace)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GetProposalQuery:
    object_id: str
