"""M28 DTOs: SMART_LINK relationship proposals.

The wire shapes of the AI-proposed relationship lifecycle — proposal
(pending), list, and the human decision (approve/reject). Frozen
dataclasses following the ``dtos/assistant.py`` doctrine: tuples for
ordered/immutable collections, plain values only.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LinkProposalOutput:
    """One AI-proposed relationship awaiting human review."""

    target_id: str
    target_type: str
    target_title: str
    #: The relationship kind the edge will take if approved.
    kind: str
    confidence: float
    #: Evidence quotes (matching metadata field pairs).
    evidence: tuple[str, ...] = field(default_factory=tuple)
    status: str = "pending"
    reviewed_by: str = ""
    reviewed_at: str | None = None


@dataclass(frozen=True)
class ProposeLinksResult:
    """Result of one propose call: the proposals created."""

    items: tuple[LinkProposalOutput, ...] = field(default_factory=tuple)
    created: int = 0


@dataclass(frozen=True)
class ListLinkProposalsResult:
    """The pending/decided SMART_LINK proposals of one object."""

    items: tuple[LinkProposalOutput, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LinkDecisionResult:
    """Outcome of a human approve/reject decision."""

    target_id: str
    target_type: str
    target_title: str
    #: Final relationship kind on approval; "" on rejection.
    kind: str
    status: str  # "approved" | "rejected"
