"""Application port: the L1 claim store (ADR-002 + ADR-019).

The single seam between the claim lifecycle (application) and durable storage
(infrastructure). The port carries domain ``Claim`` objects and ``Span``
objects, never ORM models. ``claim_id`` is the idempotency key: writing the
same claim twice is a no-op/upsert, never a duplicate row. The caller owns
the transaction (the existing object/content store convention).
"""

from __future__ import annotations

import abc

from app.domain.value_objects.claim import Claim, ClaimStatus
from app.domain.value_objects.span import Span


class ClaimStore(abc.ABC):
    @abc.abstractmethod
    def put(self, claim: Claim, spans: list[Span]) -> Claim:
        """Insert or update one claim (+ its spans) inside the caller's tx.

        Idempotent by ``claim_id``: re-writing the same id updates in place.
        """

    @abc.abstractmethod
    def get(self, claim_id: str) -> tuple[Claim, list[Span]] | None:
        """Return (claim, spans) or None when absent."""

    @abc.abstractmethod
    def by_source(self, source_document_id: str) -> list[Claim]:
        """All claims of one source document, deterministic order."""

    @abc.abstractmethod
    def by_status(self, status: ClaimStatus) -> list[Claim]:
        """Claims in a given lifecycle status (e.g. the confirmation inbox)."""

    @abc.abstractmethod
    def set_status(
        self,
        claim_id: str,
        status: ClaimStatus,
        *,
        reviewer: str | None = None,
        now: str | None = None,
    ) -> Claim:
        """Transition a claim's lifecycle status (append-safe; immutable row).

        Re-confirming or re-rejecting overwrites the *current* status field
        (the durable audit trail of WHO/WHEN lives in the review_decisions
        store, exactly like assistant reviews).
        """

    @abc.abstractmethod
    def supersede(
        self, claim_id: str, by_claim_id: str, *, now: str | None = None
    ) -> Claim:
        """Mark ``claim_id`` SUPERSEDED by ``by_claim_id`` (ADR-021, no delete)."""

    @abc.abstractmethod
    def for_source_version(self, source_document_id: str, version: int) -> list[Claim]:
        """Claims produced from a specific source version (for reprocessing /
        version-replacement cascade)."""
