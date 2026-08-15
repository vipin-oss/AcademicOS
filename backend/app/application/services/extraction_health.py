"""Extraction Health + conflict escalation (V3 M7, ADR-054).

Two review-at-scale surfaces over the durable L3 decision trail:

1. **Extraction health** — aggregates ``correct`` decisions (ADR-032 records
   `decision='correct'` when a human fixes a candidate) into per-predicate and
   per-template correction counts + a recent trend. The most-corrected
   predicates are where the extractor keeps failing — the signal for
   template/predicate fixes (which are config/data edits, not deploys).

2. **Conflict escalation** — a non-authoritative claim (PROPOSED or
   AUTO_SUGGESTED) whose value differs from an existing CONFIRMED claim of the
   same predicate is a conflict. Conflicts are surfaced side-by-side (both the
   confirmed value and the competing candidate) and are NEVER silently
   resolved: a human must decide.

Both are read-only aggregation over existing stores — no new schema, no new
writer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.ports.claim_decision_store import ClaimDecisionStore
from app.application.ports.claim_store import ClaimStore
from app.domain.value_objects.claim import Claim, ClaimStatus


def claim_value_key(claim: Claim) -> object:
    """A comparable scalar key for a claim's value (for conflict detection)."""
    value = claim.value if isinstance(claim.value, dict) else {}
    kind = value.get("kind")
    if kind in ("money", "number"):
        return value.get("amount") if kind == "money" else value.get("value")
    if kind in ("date", "text"):
        return value.get("value")
    return value.get("text")


@dataclass(frozen=True)
class CorrectionRecord:
    claim_id: str
    predicate_id: str
    reviewer: str
    created_at: str


@dataclass(frozen=True)
class ExtractionHealth:
    total_corrections: int = 0
    by_predicate: dict[str, int] = field(default_factory=dict)
    recent: tuple[CorrectionRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Conflict:
    predicate_id: str
    confirmed_claim_id: str
    confirmed_value: object
    candidate_claim_id: str
    candidate_value: object
    candidate_status: str


class ExtractionHealthService:
    """Aggregate correction signal over the decision trail."""

    def __init__(self, claims: ClaimStore, decisions: ClaimDecisionStore) -> None:
        self._claims = claims
        self._decisions = decisions

    def health(self, *, recent_limit: int = 200) -> ExtractionHealth:
        corrections = self._decisions.recent_corrections(limit=recent_limit)
        by_predicate: dict[str, int] = {}
        recent: list[CorrectionRecord] = []
        for record in corrections:
            stored = self._claims.get(record.subject_id)
            predicate_id = stored[0].predicate_id if stored is not None else "unknown"
            by_predicate[predicate_id] = by_predicate.get(predicate_id, 0) + 1
            recent.append(
                CorrectionRecord(
                    claim_id=record.subject_id,
                    predicate_id=predicate_id,
                    reviewer=record.reviewer,
                    created_at=record.created_at,
                )
            )
        return ExtractionHealth(
            total_corrections=len(corrections),
            by_predicate=by_predicate,
            recent=tuple(recent),
        )


class ConflictReport:
    """Find non-authoritative candidates that contradict CONFIRMED facts."""

    def __init__(self, claims: ClaimStore) -> None:
        self._claims = claims

    def conflicts(self) -> tuple[Conflict, ...]:
        """Every (predicate) where a PROPOSED/AUTO_SUGGESTED value differs from
        a CONFIRMED value. Never resolved here — a human decides."""
        out: list[Conflict] = []
        seen_predicates: set[str] = set()
        for status in (ClaimStatus.PROPOSED, ClaimStatus.AUTO_SUGGESTED):
            for candidate in self._claims.by_status(status):
                if candidate.predicate_id in seen_predicates:
                    continue
                confirmed = self._claims.confirmed_by_predicate(candidate.predicate_id)
                for confirmed_claim, _spans in confirmed:
                    if claim_value_key(confirmed_claim) == claim_value_key(candidate):
                        continue  # same value — no conflict
                    out.append(
                        Conflict(
                            predicate_id=candidate.predicate_id,
                            confirmed_claim_id=confirmed_claim.claim_id,
                            confirmed_value=claim_value_key(confirmed_claim),
                            candidate_claim_id=candidate.claim_id,
                            candidate_value=claim_value_key(candidate),
                            candidate_status=candidate.status.value,
                        )
                    )
                    seen_predicates.add(candidate.predicate_id)
                    break
        return tuple(out)


__all__ = [
    "Conflict",
    "ConflictReport",
    "CorrectionRecord",
    "ExtractionHealth",
    "ExtractionHealthService",
    "claim_value_key",
]
