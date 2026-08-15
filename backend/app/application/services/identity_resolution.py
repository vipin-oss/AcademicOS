"""Identity resolution (V3 M17, ADR-064).

Surfaces candidate identity matches (same person under different spellings /
IDs) for HUMAN review. Never auto-merges: merge/split/redirect is a human
decision recorded as data (no automatic irreversible merge — the blueprint's
hard constraint). Matching is deterministic:

- transliteration match (``Vipin`` ↔ ``विपिन``) via :func:`match_key`;
- institutional ID / ORCID / DOI exact match on a declared identifier.

The service is read-only: it proposes, never mutates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.services.transliteration import match_key
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.enums import ObjectType
from app.domain.value_objects.object_id import ObjectId


@dataclass(frozen=True)
class IdentityCandidate:
    subject_id: str
    match_id: str
    reason: str  # "transliteration" | "identifier"
    score: float


@dataclass(frozen=True)
class ResolutionReport:
    subject_id: str
    candidates: tuple[IdentityCandidate, ...] = field(default_factory=tuple)


class IdentityResolutionService:
    """Proposes identity candidates; a human decides merge/split/redirect."""

    def __init__(self, repository: ObjectRepository) -> None:
        self._repository = repository

    def find_candidates(
        self,
        subject_id: str,
        *,
        identifier: str | None = None,
    ) -> ResolutionReport:
        subject = self._repository.get_by_id(ObjectId(subject_id))
        if subject is None:
            return ResolutionReport(subject_id=subject_id)

        subject_key = match_key(subject.title)
        candidates: list[IdentityCandidate] = []

        for other in self._repository.find(object_type=ObjectType.USER):
            if str(other.id) == subject_id:
                continue
            other_key = match_key(other.title)
            if subject_key and other_key and subject_key == other_key:
                candidates.append(
                    IdentityCandidate(
                        subject_id=subject_id,
                        match_id=str(other.id),
                        reason="transliteration",
                        score=1.0,
                    )
                )
            if identifier:
                other_identifier = _identifier_of(other)
                if other_identifier and other_identifier == identifier:
                    candidates.append(
                        IdentityCandidate(
                            subject_id=subject_id,
                            match_id=str(other.id),
                            reason="identifier",
                            score=1.0,
                        )
                    )

        # de-duplicate by (match_id, reason); keep highest score
        seen: dict[tuple[str, str], IdentityCandidate] = {}
        for c in candidates:
            key = (c.match_id, c.reason)
            if key not in seen or c.score > seen[key].score:
                seen[key] = c
        return ResolutionReport(
            subject_id=subject_id,
            candidates=tuple(sorted(seen.values(), key=lambda c: (-c.score, c.match_id))),
        )


def _identifier_of(obj) -> str | None:
    raw = obj.metadata.get_value("orcid") if obj.metadata else None
    if not raw:
        raw = obj.metadata.get_value("institutional_id") if obj.metadata else None
    if not raw:
        raw = obj.metadata.get_value("doi") if obj.metadata else None
    return str(raw) if raw else None


__all__ = [
    "IdentityCandidate",
    "IdentityResolutionService",
    "ResolutionReport",
]
