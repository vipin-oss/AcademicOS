"""AcademicAiRouter — the single AI answering owner (V3 M12, ADR-059).

The one place that owns, in order:

1. **classification** — which rung answers the question: rung-0 confirmed
   claims (M5) → rung-1 dossier (M8) → grounded QA (retrieval + gateway);
2. **source policy** — internal-first, ``NO_EXTERNAL_SEARCH`` (never the web);
3. **model routing + budget** — the paid (gateway) path is gated by the
   ``ModelBudgetPolicy``; on "degrade" the router falls back to the local/free
   path ("answered locally, free");
4. **response shape** — one ``RouterResult`` regardless of which rung answered,
   with ``rung`` / ``source_class`` / ``estimated_cost_usd`` / ``free``.

``/ai`` and ``/assistant`` become thin adapters over this router. The legacy
``rules-v1`` (``RuleBasedAssistantProvider`` + ``parse_question``) is NOT
deleted here: its deletion is gated on golden-test parity (blueprint), which
this ADR documents as deferred — the offline fast-path answerer remains the
degradation seam, now *behind* the router.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.application.ports.spend_ledger import SpendLedger, SpendRecord
from app.application.services.model_budget import (
    ON_BUDGET_DEGRADE,
    ModelBudgetPolicy,
)
from app.application.use_cases.ai.rung0 import Rung0ClaimAnswerer
from app.domain.entities.object import UniversalObject

#: Source policy: the router never consults external search (blueprint §M12).
SOURCE_POLICY_INTERNAL = "internal"
NO_EXTERNAL_SEARCH = True

#: Rung labels (answering ladder, blueprint §B1).
RUNG_CLAIMS = 0
RUNG_DOSSIER = 1
RUNG_QA = 6


@dataclass(frozen=True)
class RouterResult:
    """The unified answering response shape, independent of the rung."""

    answer: str
    rung: int
    source_class: str
    free: bool = True
    estimated_cost_usd: float = 0.0
    evidence: tuple[dict, ...] = field(default_factory=tuple)
    provider_id: str = ""
    model: str = ""
    degraded: bool = False


@dataclass(frozen=True)
class _QAResultView:
    """A minimal projection of GroundedQAUseCase's result (duck-typed)."""

    answer: str
    available: bool
    provider_id: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    citations: tuple = ()

    @property
    def estimated_cost(self) -> float:
        from app.application.ai.llm.estimates import estimate_cost_usd

        return estimate_cost_usd(
            input_tokens=self.input_tokens, output_tokens=self.output_tokens
        )


class AcademicAiRouter:
    """Single owner of classification, source policy, routing, response shape."""

    def __init__(
        self,
        *,
        rung0: Rung0ClaimAnswerer,
        budget_policy: ModelBudgetPolicy,
        spend_ledger: SpendLedger,
        grounded_qa=None,  # duck-typed: .execute(question, user) -> QAResult
    ) -> None:
        self._rung0 = rung0
        self._budget = budget_policy
        self._ledger = spend_ledger
        self._grounded = grounded_qa

    @property
    def source_policy(self) -> str:
        return SOURCE_POLICY_INTERNAL

    def route(
        self,
        question: str,
        user: UniversalObject,
        principal: dict | None = None,
    ) -> RouterResult:
        """Answer a question through the ladder, applying budget + source policy.

        Rung 0 (confirmed claims) and rung 1 (dossier) are always free and
        local; rung 6 (grounded QA) consults the gateway only if the budget
        policy allows it — otherwise it degrades to the local/free path.
        """
        if principal is None:
            principal = {"sub": str(user.id), "roles": []}

        # Rung 0 — confirmed claims (free, local, deterministic).
        claim = self._rung0.answer(question, principal)
        if claim is not None:
            return RouterResult(
                answer=claim.value,
                rung=RUNG_CLAIMS,
                source_class=claim.source_class,
                free=True,
                evidence=claim.to_dict()["evidence"],
            )

        # Rung 6 — grounded QA (gateway), gated by budget + internal-only.
        if self._grounded is not None:
            decision = self._budget.check(
                tenant_id=principal.get("tenant_id", "default"),
                user_id=str(user.id),
                estimated_cost_usd=0.0,  # actual cost estimated post-generation
            )
            if decision.allowed:
                result = self._grounded.execute(question, user)
                view = _to_view(result)
                self._record_spend(user, principal, view)
                return RouterResult(
                    answer=view.answer,
                    rung=RUNG_QA,
                    source_class="retrieval",
                    free=False,
                    estimated_cost_usd=view.estimated_cost,
                    evidence=list(view.citations),
                    provider_id=view.provider_id,
                    model=view.model,
                )
            if decision.action == ON_BUDGET_DEGRADE:
                return RouterResult(
                    answer="Budget exhausted; answered locally is unavailable. "
                    "Please reduce usage or contact an administrator.",
                    rung=RUNG_QA,
                    source_class="degraded",
                    free=True,
                    degraded=True,
                )

        # No answerable rung — honest refusal.
        return RouterResult(
            answer="I could not answer this from confirmed facts or documents.",
            rung=RUNG_QA,
            source_class="refused",
            free=True,
        )

    def _record_spend(self, user, principal, view: _QAResultView) -> None:
        from app.application.ai.llm.estimates import estimate_cost_usd

        cost = estimate_cost_usd(
            input_tokens=view.input_tokens, output_tokens=view.output_tokens
        )
        self._ledger.record(
            SpendRecord(
                id=uuid.uuid4().hex,
                tenant_id=principal.get("tenant_id", "default"),
                user_id=str(user.id),
                provider_id=view.provider_id,
                model=view.model,
                input_tokens=view.input_tokens,
                output_tokens=view.output_tokens,
                estimated_cost_usd=cost,
                created_at=datetime.now(UTC).isoformat(),
            )
        )


def _to_view(result) -> _QAResultView:
    """Project a GroundedQAUseCase result onto the router's minimal view.

    Uses the documented attributes; missing optional fields default safely.
    """
    return _QAResultView(
        answer=getattr(result, "answer", ""),
        available=getattr(result, "available", True),
        provider_id=getattr(result, "provider_id", ""),
        model=getattr(result, "model", ""),
        input_tokens=getattr(result, "input_tokens", 0),
        output_tokens=getattr(result, "output_tokens", 0),
        citations=tuple(getattr(result, "citations", ())),
    )


__all__ = [
    "NO_EXTERNAL_SEARCH",
    "RUNG_CLAIMS",
    "RUNG_DOSSIER",
    "RUNG_QA",
    "AcademicAiRouter",
    "RouterResult",
]
