"""Dossier aggregates (V3 M8 — answering-ladder rung 1).

Precomputed, cached aggregates for the common "how many / how much" questions
that rung-0 claims alone cannot answer (e.g. object counts by type, total
sanctioned amount). Rung 1 of the Answering Ladder (blueprint §B1): dossier
lookups are ₹0 and answered without retrieval or an LLM.

Two forms, same law:

- the cached aggregate (this module) is the always-available form;
- a materialized table rebuilt by outbox consumers is the scale-time form
  (SCALE_LAW); both are invalidated by the SAME outbox/claim-write paths
  (blueprint law 22), so swapping the backing store is invisible to callers.

Aggregates are computed over the authoritative repositories (never the
derived index) and cached behind :class:`FactCache`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.ports.claim_store import ClaimStore
from app.application.services.fact_cache import FACT_CACHE, FactCache
from app.domain.repositories.object_repository import ObjectRepository
from app.domain.value_objects.claim import ClaimStatus


@dataclass(frozen=True)
class Dossier:
    """A bundle of rung-1 aggregates (extensible, additive)."""

    object_counts: dict[str, int] = field(default_factory=dict)
    confirmed_claims: int = 0
    sanctioned_total: float | None = None


def _sanctioned_total(claims: ClaimStore) -> float | None:
    total = 0.0
    found = False
    for claim, _spans in claims.confirmed_by_predicate("sanctioned_amount"):
        value = claim.value if isinstance(claim.value, dict) else {}
        if value.get("kind") == "money" and isinstance(value.get("amount"), int | float):
            total += value["amount"]
            found = True
    return total if found else None


class DossierService:
    """Cached materialized aggregates (rung 1)."""

    def __init__(
        self,
        objects: ObjectRepository,
        claims: ClaimStore,
        cache: FactCache | None = None,
    ) -> None:
        self._objects = objects
        self._claims = claims
        self._cache = cache or FACT_CACHE

    def dossier(self) -> Dossier:
        key = "dossier:v1"
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        object_counts: dict[str, int] = {}
        for obj in self._objects.list():
            object_counts[obj.object_type.value] = (
                object_counts.get(obj.object_type.value, 0) + 1
            )
        confirmed = self._claims.by_status(ClaimStatus.CONFIRMED)
        dossier = Dossier(
            object_counts=object_counts,
            confirmed_claims=len(confirmed),
            sanctioned_total=_sanctioned_total(self._claims),
        )
        self._cache.put(key, dossier)
        return dossier


__all__ = ["Dossier", "DossierService"]
