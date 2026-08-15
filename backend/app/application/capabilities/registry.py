"""Frozen capability registry (Freeze Contract §13.5.5 / Part 5).

Additive after L0 only via ADR amendment + golden file + (later) a tool.
This module does not route questions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilitySpec:
    """One frozen capability. ``capability_id`` is the stable key."""

    capability_id: str
    description: str


#: Exact frozen set. Order is the contract order (inventory last in the
#: L0 brief's list; stored here in a stable documented sequence).
CAPABILITIES: tuple[CapabilitySpec, ...] = (
    CapabilitySpec("inventory", "List what knowledge/data the system holds."),
    CapabilitySpec("lookup", "Fetch one known record by identity or unique key."),
    CapabilitySpec("list", "Enumerate matching records."),
    CapabilitySpec("search", "Retrieve by free-text / semantic query."),
    CapabilitySpec("count", "Return a deterministic count (never LLM arithmetic)."),
    CapabilitySpec("filter", "Restrict a set by structured predicates."),
    CapabilitySpec("summarize", "Condense accessible evidence."),
    CapabilitySpec("compare", "Contrast two or more entities or documents."),
    CapabilitySpec("aggregate", "Deterministic aggregation over a filtered set."),
    CapabilitySpec("timeline", "Order events or documents in time."),
    CapabilitySpec("document_qa", "Answer from a named document's source text."),
    CapabilitySpec("relationship", "Traverse or explain typed graph edges."),
    CapabilitySpec("cross_domain", "Join evidence across academic domains."),
    CapabilitySpec("absence", "Honestly report that something is not present."),
    CapabilitySpec("temporal", "Answer a time-bounded question."),
    CapabilitySpec("navigate", "Point the user at the right module or object."),
    CapabilitySpec("clarify", "Ask when the question is ambiguous."),
    CapabilitySpec("refuse", "Decline when evidence, ACL, or policy forbids an answer."),
)

FROZEN_CAPABILITY_IDS: tuple[str, ...] = tuple(spec.capability_id for spec in CAPABILITIES)


def is_frozen_capability(capability_id: str) -> bool:
    return capability_id in FROZEN_CAPABILITY_IDS
