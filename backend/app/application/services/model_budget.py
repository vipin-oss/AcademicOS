"""Model budget policy + spend ledger (V3 M12, ADR-059).

The single owner of "who may spend how much on AI": per-tenant budget and
per-user cap, with an explicit ``on_budget_exhausted`` policy (block | degrade
| allow). The policy reads the append-only spend ledger; it never mutates it
(the router records spend after a successful generation).

Blueprints: "Model budget is tenant policy, enforced centrally, with a spend
ledger" (B2 #24); "answered locally, free" vs estimated cost (M12).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.ports.spend_ledger import SpendLedger

#: on_budget_exhausted actions.
ON_BUDGET_BLOCK = "block"
ON_BUDGET_DEGRADE = "degrade"
ON_BUDGET_ALLOW = "allow"

_ON_BUDGET_ACTIONS = (ON_BUDGET_BLOCK, ON_BUDGET_DEGRADE, ON_BUDGET_ALLOW)


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    action: str
    reason: str = ""


@dataclass(frozen=True)
class ModelBudgetPolicyConfig:
    tenant_budget_usd: float = 0.0
    per_user_cap_usd: float = 0.0
    on_budget_exhausted: str = ON_BUDGET_DEGRADE


class ModelBudgetPolicy:
    """Central budget enforcement over the spend ledger."""

    def __init__(self, ledger: SpendLedger, config: ModelBudgetPolicyConfig) -> None:
        self._ledger = ledger
        self._config = config

    def check(self, *, tenant_id: str, user_id: str, estimated_cost_usd: float) -> BudgetDecision:
        """Whether a call of ``estimated_cost_usd`` may proceed.

        A tenant budget / per-user cap of 0.0 means "unlimited" (no cap). When
        a cap is set and would be exceeded, the ``on_budget_exhausted`` action
        decides: block (deny), degrade (deny the paid path — the caller falls
        back to the local/free path), or allow (permit with a reason).
        """
        if self._config.tenant_budget_usd > 0.0:
            spent = self._ledger.total_for_tenant(tenant_id)
            if spent + estimated_cost_usd > self._config.tenant_budget_usd:
                return self._exhausted("tenant budget exhausted")
        if self._config.per_user_cap_usd > 0.0:
            spent = self._ledger.total_for_user(user_id)
            if spent + estimated_cost_usd > self._config.per_user_cap_usd:
                return self._exhausted("user cap exhausted")
        return BudgetDecision(allowed=True, action="allow")

    def _exhausted(self, reason: str) -> BudgetDecision:
        action = self._config.on_budget_exhausted
        if action == ON_BUDGET_BLOCK:
            return BudgetDecision(allowed=False, action=action, reason=reason)
        if action == ON_BUDGET_DEGRADE:
            # Deny the paid path; the router degrades to the local/free rung.
            return BudgetDecision(allowed=False, action=action, reason=reason)
        return BudgetDecision(allowed=True, action=action, reason=reason)


__all__ = [
    "ON_BUDGET_ALLOW",
    "ON_BUDGET_BLOCK",
    "ON_BUDGET_DEGRADE",
    "BudgetDecision",
    "ModelBudgetPolicy",
    "ModelBudgetPolicyConfig",
]
