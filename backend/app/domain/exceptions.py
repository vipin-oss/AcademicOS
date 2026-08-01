"""Domain exceptions — framework-independent, no HTTP/DB concepts.

Frozen reference: these are the only error types the domain layer raises.
They are intentionally free of status codes and transport details; the API
layer translates them into responses much later (in infrastructure).

Note on FR-MET-009: ``Metadata.with_entry`` *silently keeps* the human value
rather than raising, because the safer behavior is to ignore the conflicting
AI write. ``MetadataOverwriteError`` is provided for deployments that prefer a
hard failure instead.
"""
from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain-level errors."""

    code: str = "domain_error"


class ObjectNotFoundError(DomainError):
    code = "object_not_found"


class InvalidStateTransitionError(DomainError):
    code = "invalid_state_transition"

    def __init__(self, current: object, target: object) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition status {current} -> {target}")


class RelationshipConflictError(DomainError):
    code = "relationship_conflict"


class MetadataOverwriteError(DomainError):
    code = "metadata_overwrite"

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"Refusing to overwrite human-asserted metadata key {key!r}")


class InvariantViolationError(DomainError):
    code = "invariant_violation"
